#!/usr/bin/env node
/* =========================================================
   Testador das missões (.trycmd) do Guia Rust.
   1) Confere a estrutura de cada caixa e avalia as metas src
      no pre.solucao (e no pre.script, que não pode já cumprir
      todas as metas src).
   2) Com o cargo instalado (padrão), COMPILA e RODA cada
      solução de verdade (cargo run, ou o data-cmd da caixa,
      como "cargo test") num projeto temporário e confere TODAS
      as metas (out, outre, erro, semerro) na saída real.
      Também confere as metas no pre.saida-ok guardado.

   Uso:
     node tools/testar-missoes.js
     node tools/testar-missoes.js --secao "Começando"
     node tools/testar-missoes.js --sem-compilar
   ========================================================= */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const os = require("os");
const cp = require("child_process");
const ROOT = path.resolve(__dirname, "..");
const SITE = path.join(ROOT, "assets", "site.js");
const RODE_LOCAL = path.join(ROOT, "assets", "rode-local.js");

function uso() {
  return [
    "Uso: node tools/testar-missoes.js [--secao NOME]",
    "  --secao         filtra pela seção do NIVEIS (ex.: Começando)",
    "  --sem-compilar  não compila nem roda as soluções (só estrutura e metas src)"
  ].join("\n");
}

function args() {
  const out = { secao: null, compilar: true };
  const a = process.argv.slice(2);
  for (let i = 0; i < a.length; i++) {
    if (a[i] === "--secao" && a[i + 1]) out.secao = a[++i];
    else if (a[i] === "--sem-compilar") out.compilar = false;
    else if (a[i] === "--help" || a[i] === "-h") { console.log(uso()); process.exit(0); }
    else {
      console.error("Opção desconhecida: " + a[i] + "\n" + uso());
      process.exit(2);
    }
  }
  return out;
}

function carregarNiveis() {
  const src = fs.readFileSync(SITE, "utf8");
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(src.replace(/\n\(\s*function\s*\(\s*\)\s*\{[\s\S]*$/, "\n") + "\nthis.NIVEIS = NIVEIS;\n", ctx, { filename: "site.js#NIVEIS" });
  if (!Array.isArray(ctx.NIVEIS)) throw new Error("não achei NIVEIS em assets/site.js");
  return ctx.NIVEIS;
}

function carregarAvaliador() {
  const src = fs.readFileSync(RODE_LOCAL, "utf8");
  const m = src.match(/\/\* cmf-avaliador:inicio[^*]*\*\/\s*([\s\S]*?)\s*\/\* cmf-avaliador:fim \*\//);
  if (!m) throw new Error("não achei o trecho cmf-avaliador em rode-local.js.");
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(m[1] + "\nthis.cmfAvaliar = cmfAvaliar;\nthis.cmfNormaliza = cmfNormaliza;\n", ctx, { filename: "rode-local.js#avaliador" });
  if (typeof ctx.cmfAvaliar !== "function") throw new Error("o trecho recortado não exportou cmfAvaliar.");
  return ctx;
}

function trim(s) { return String(s || "").replace(/^\n+/, "").replace(/\s+$/, ""); }

function caixasDe(html) {
  const out = [];
  const re = /<div\s+class="[^"]*\btrycmd\b[^"]*"[^>]*>([\s\S]*?)<\/div>/gi;
  // fallback: data-goal may be on the opening tag; capture the tag + body until next trycmd or end of reasonable block
  const re2 = /<div([^>]*\btrycmd\b[^>]*)>([\s\S]*?)(?=<div[^>]*\btrycmd\b|<\/div>\s*<\/div>\s*<hr>|<h2>Resumo|$)/gi;
  let m;
  const src = html;
  const tagRe = /<div\b([^>]*\btrycmd\b[^>]*)>/gi;
  const indices = [];
  while ((m = tagRe.exec(src))) indices.push({ start: m.index, attrs: m[1], bodyStart: m.index + m[0].length });
  for (let i = 0; i < indices.length; i++) {
    const end = i + 1 < indices.length ? indices[i + 1].start : src.length;
    const chunk = src.slice(indices[i].start, end);
    const attrs = indices[i].attrs;
    const gm = /\bdata-goal="([^"]*)"/.exec(attrs) || /\bdata-goal="([^"]*)"/.exec(chunk);
    const script = /<pre\s+class="script"[^>]*>([\s\S]*?)<\/pre>/.exec(chunk);
    const solucao = /<pre\s+class="solucao"[^>]*>([\s\S]*?)<\/pre>/.exec(chunk);
    const saidaOk = /<pre\s+class="saida-ok"[^>]*>([\s\S]*?)<\/pre>/.exec(chunk);
    const cmdm = /\bdata-cmd="([^"]*)"/.exec(attrs);
    out.push({
      goal: gm ? gm[1].replace(/&gt;/g, ">").replace(/&lt;/g, "<").replace(/&amp;/g, "&") : "",
      script: script ? trim(decode(script[1])) : "",
      solucao: solucao ? trim(decode(solucao[1])) : "",
      saidaOk: saidaOk ? trim(decode(saidaOk[1])) : "",
      cmd: cmdm ? decode(cmdm[1]) : "cargo run",
      temSol: !!solucao
    });
  }
  return out;
}

function decode(s) {
  return s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&").replace(/&quot;/g, '"');
}

function soSrc(goal) {
  const partes = String(goal || "").split(";;").map((p) => p.trim()).filter(Boolean);
  return partes.filter((p) => {
    const tipo = (p.indexOf(":") === -1 ? p : p.slice(0, p.indexOf(":"))).trim();
    return tipo === "src";
  });
}

let PROJ = null;
function temCargo() {
  try { cp.execFileSync("cargo", ["--version"], { stdio: "ignore" }); return true; } catch (e) { return false; }
}
function rodarSolucao(codigo, cmd) {
  if (!PROJ) {
    PROJ = fs.mkdtempSync(path.join(os.tmpdir(), "guia-rust-missao-"));
    fs.mkdirSync(path.join(PROJ, "src"));
    fs.writeFileSync(path.join(PROJ, "Cargo.toml"), '[package]\nname = "missao"\nversion = "0.1.0"\nedition = "2024"\n\n[dependencies]\n');
  }
  fs.writeFileSync(path.join(PROJ, "src", "main.rs"), codigo + "\n");
  const partes = cmd.split(/\s+/);
  const r = cp.spawnSync(partes[0], partes.slice(1), { cwd: PROJ, encoding: "utf8", timeout: 120000, env: Object.assign({}, process.env, { CARGO_TERM_COLOR: "never" }) });
  return (r.stderr || "") + (r.stdout || "");
}

(function main() {
  const opt = args();
  const niveis = carregarNiveis();
  const av = carregarAvaliador();
  let paginas = [];
  niveis.forEach((n) => n.grupos.forEach((g) => g.itens.forEach((i) => {
    const pronta = true;
    if (opt.secao && g.grupo !== opt.secao) return;
    paginas.push({ href: i[0], titulo: i[1], secao: g.grupo, pronta });
  })));

  let falhou = 0, testadas = 0, puladas = 0, compiladas = 0;
  const compilar = opt.compilar && temCargo();
  if (opt.compilar && !compilar) console.log("(cargo não encontrado: pulando a compilação das soluções)");
  for (const p of paginas) {
    const arq = path.join(ROOT, p.href);
    if (!p.pronta) { puladas++; continue; }
    if (!fs.existsSync(arq)) {
      console.log("✗ " + p.href + "  marcada pronta, mas o arquivo não existe");
      falhou++; continue;
    }
    const html = fs.readFileSync(arq, "utf8");
    const caixas = caixasDe(html);
    if (!caixas.length) {
      console.log("· " + p.href + "  sem .trycmd");
      continue;
    }
    caixas.forEach((c, idx) => {
      const nome = p.href + " caixa " + (idx + 1);
      if (!c.goal) { console.log("· " + nome + "  sem data-goal"); return; }
      if (!c.temSol) { console.log("✗ " + nome + "  missão sem pre.solucao"); falhou++; return; }
      testadas++;
      const metasSrc = soSrc(c.goal);
      const problemasExec = [];
      const conferirSaida = (rotulo, saida) => {
        const r = av.cmfAvaliar(c.goal, c.solucao, saida);
        const ruins = r.filter((m) => m.ok === false);
        if (ruins.length) problemasExec.push(rotulo + " não cumpre: " + ruins.map((m) => m.desc + (m.falha ? " (" + m.falha + ")" : "")).join(" ;; "));
      };
      if (c.saidaOk) conferirSaida("a saida-ok guardada", c.saidaOk);
      else if (/(^|;;)\s*(out|outre|erro)\b/.test(c.goal)) problemasExec.push("meta out/outre/erro sem pre.saida-ok");
      if (compilar) {
        compiladas++;
        conferirSaida("a saída real de `" + c.cmd + "`", rodarSolucao(c.solucao, c.cmd));
      }
      if (problemasExec.length) {
        console.log("✗ " + nome + "  " + problemasExec.join(" | "));
        falhou++;
        return;
      }
      if (!metasSrc.length) {
        console.log("✓ " + nome + "  (sem meta src)");
        return;
      }
      const goalSrc = metasSrc.join(";;");
      const rSol = av.cmfAvaliar(goalSrc, c.solucao, "");
      const falhasSol = rSol.filter((m) => m.ok !== true);
      if (falhasSol.length) {
        console.log("✗ " + nome + "  a solução não cumpre src: " + falhasSol.map((m) => m.desc || m.falha).join(" ;; "));
        falhou++;
      } else {
        const iguais = c.script === c.solucao;
        const rIni = av.cmfAvaliar(goalSrc, c.script, "");
        const iniOk = rIni.every((m) => m.ok === true);
        if (iniOk && !iguais && c.script) {
          console.log("✗ " + nome + "  o script inicial já cumpre as metas src");
          falhou++;
        } else {
          console.log("✓ " + nome);
        }
      }
    });
  }
  if (PROJ) fs.rmSync(PROJ, { recursive: true, force: true });
  console.log("\n" + testadas + " missão(ões) conferida(s), " + compiladas + " compilada(s) e rodada(s) de verdade, " + falhou + " com problema.");
  process.exit(falhou ? 1 : 0);
})();
