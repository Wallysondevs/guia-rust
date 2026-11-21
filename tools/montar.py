#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monta o Guia Rust a partir de aulas/*.aula.

Cada exemplo é COMPILADO E RODADO DE VERDADE como a usuária `ana`
em /home/ana/projetos/<projeto> (rustc/cargo do rustup dela), e a saída
real entra na página. Nada de saída inventada. Os resultados ficam em
cache em tools/_cache/ (fora do git), pela soma dos arquivos + comando.

Formato de uma aula (aulas/NN-slug.aula):

    ---
    slug: variaveis
    menu: Variáveis e mut
    titulo: <title> da página
    desc: meta description
    h1: HTML do h1
    nivel: n1
    grupo: Fundamentos
    ---
    HTML livre…
    ::: exemplo NOME [cmd="cargo run"] [falha]
    código do src/main.rs
    --- arquivo src/outro.rs
    …
    :::
    ::: terminal NOME [cwd=~/projetos]
    $ comando
    :::
    ::: missao goal="src:…;;out:…" [cmd="cargo test"]
    enunciado (HTML)
    --- script
    código inicial
    --- solucao
    solução (compilada e rodada aqui)
    :::
    ::: mc N
    Pergunta
    - opção…
    :::
    ::: ex
    Enunciado
    código com [[resposta|alternativa]]
    :::

Uso: python3 tools/montar.py [--sem-cache] [slug…]
"""
import hashlib, html, json, os, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AULAS = ROOT / "aulas"
CACHE = ROOT / "tools" / "_cache"
STAGE = Path("/tmp/guia-rust-stage")
PROJETOS = "/home/ana/projetos"
AMB = ["sudo", "-u", "ana", "env", "-i", "HOME=/home/ana", "USER=ana", "LOGNAME=ana",
       "PATH=/home/ana/.cargo/bin:/usr/local/bin:/usr/bin:/bin", "CARGO_TERM_COLOR=never",
       "LANG=C.UTF-8", "TERM=dumb"]
SEM_CACHE = "--sem-cache" in sys.argv
SO = [a for a in sys.argv[1:] if not a.startswith("--")]

NIVEL_NOME = {
    "n1": ("Nível 1 · Iniciante", "Iniciante", "Rust do zero: cargo, tipos, ownership, structs e enums"),
    "n2": ("Nível 2 · Intermediário", "Intermediário", "Erros, coleções, traits, generics, closures e testes"),
    "n3": ("Nível 3 · Avançado", "Avançado", "Smart pointers, concorrência, macros, unsafe e projeto final"),
}

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def attr(s):
    return esc(s).replace('"', "&quot;")

def toml(nome, extra=""):
    return f'[package]\nname = "{nome}"\nversion = "0.1.0"\nedition = "2024"\n\n[dependencies]\n{extra}'

# ---------------------------------------------------------------- execução real
def rodar_bash(script, cwd):
    """Roda um script bash como ana; devolve stdout+stderr misturados."""
    r = subprocess.run(AMB + ["bash", "-c", f"cd {cwd} && {script}"],
                       capture_output=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, timeout=600)
    return r.returncode, r.stdout

def chave(*partes):
    h = hashlib.sha256()
    for p in partes:
        h.update(json.dumps(p, sort_keys=True, ensure_ascii=False).encode())
    return h.hexdigest()[:20]

def cache_get(k):
    f = CACHE / (k + ".json")
    if f.exists() and not SEM_CACHE:
        return json.loads(f.read_text(encoding="utf-8"))
    return None

def cache_put(k, v):
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / (k + ".json")).write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")

def preparar_projeto(nome, arquivos):
    """Recria /home/ana/projetos/<nome> do zero com os arquivos dados."""
    if STAGE.exists():
        shutil.rmtree(STAGE)
    (STAGE / nome).mkdir(parents=True)
    arqs = dict(arquivos)
    if "Cargo.toml" not in arqs:
        arqs["Cargo.toml"] = toml(nome)
    for rel, txt in arqs.items():
        f = STAGE / nome / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(txt.rstrip("\n") + "\n", encoding="utf-8")
    os.system(f"chmod -R a+rX {STAGE}")
    subprocess.run(AMB + ["bash", "-c", f"rm -rf {PROJETOS}/{nome} && cp -r {STAGE}/{nome} {PROJETOS}/{nome}"], check=True)

def rodar_projeto(nome, arquivos, cmd):
    k = chave("proj", nome, arquivos, cmd)
    c = cache_get(k)
    if c:
        return c["rc"], c["out"]
    preparar_projeto(nome, arquivos)
    rc, out = rodar_bash(cmd, f"{PROJETOS}/{nome}")
    out = limpar(out)
    cache_put(k, {"rc": rc, "out": out})
    return rc, out

def rodar_terminal(nome, cmds, cwd, preparo):
    """Roda vários comandos em sequência (mesma sessão), separando a saída de cada um."""
    k = chave("term", nome, cmds, cwd, preparo)
    c = cache_get(k)
    if c:
        return c["saidas"]
    if preparo is not None:
        preparar_projeto(nome, preparo)
    else:
        subprocess.run(AMB + ["bash", "-c", f"rm -rf {PROJETOS}/{nome}"], check=True)
    marca = "@@GUIA-RUST-FIM@@"
    script = ""
    for c_ in cmds:
        script += f"{{ {c_} ; }} 2>&1; echo \"{marca}$?\"\n"
    rc, out = rodar_bash(script, cwd.replace("~", "/home/ana"))
    partes = out.split(marca)
    saidas = []
    for i in range(len(cmds)):
        p = partes[i]
        if i > 0:
            p = p.split("\n", 1)[1] if "\n" in p else ""
        saidas.append(limpar(p))
    cache_put(k, {"saidas": saidas})
    return saidas

def limpar(s):
    s = s.replace("\r", "")
    s = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", s)
    return s.rstrip("\n")

# ---------------------------------------------------------------- blocos
def bloco_codigo(arquivos):
    out = []
    for rel, txt in arquivos.items():
        if rel == "Cargo.toml" and txt.strip().startswith("[package]") and "[dependencies]\n" == txt.split("[dependencies]")[-1][:1] + "":
            pass
        out.append(f'<pre class="file" data-file="{attr(rel)}">{esc(txt.rstrip())}</pre>')
    return "\n".join(out)

def term(cwd, pares):
    linhas = []
    for cmd, saida in pares:
        linhas.append("$ " + cmd)
        if saida:
            linhas.extend(saida.split("\n"))
    return f'<pre class="term" data-cwd="{attr(cwd)}">{esc(chr(10).join(linhas))}</pre>'

def parse_opts(s):
    opts = {}
    for m in re.finditer(r'(\w+)="([^"]*)"|(\w+)=(\S+)|(\S+)', s):
        if m.group(1): opts[m.group(1)] = m.group(2)
        elif m.group(3): opts[m.group(3)] = m.group(4)
        else: opts.setdefault("_pos", []).append(m.group(5))
    return opts

def secoes(corpo, primeira):
    """Divide em seções '--- nome resto'."""
    atual, resto = primeira, ""
    out = {}
    ordem = []
    buf = []
    for l in corpo.split("\n"):
        m = re.match(r"^--- (\S+)(?: (.*))?$", l)
        if m:
            out[(atual, resto)] = "\n".join(buf).strip("\n")
            ordem.append((atual, resto))
            atual, resto, buf = m.group(1), (m.group(2) or ""), []
        else:
            buf.append(l)
    out[(atual, resto)] = "\n".join(buf).strip("\n")
    ordem.append((atual, resto))
    return out, ordem

ERROS = []
MISSOES = 0

def b_exemplo(opts, corpo, slug):
    nome = opts["_pos"][0]
    cmd = opts.get("cmd", "cargo run")
    sec, ordem = secoes(corpo, "codigo")
    arquivos = {}
    for (k, r) in ordem:
        if k == "codigo": arquivos["src/main.rs"] = sec[(k, r)]
        elif k == "arquivo": arquivos[r.strip()] = sec[(k, r)]
    if not arquivos.get("src/main.rs"):
        arquivos.pop("src/main.rs", None)
    rc, out = rodar_projeto(nome, arquivos, cmd)
    falha = "falha" in opts.get("_pos", [])
    if falha and rc == 0:
        ERROS.append(f"{slug}: exemplo {nome} deveria falhar e rodou (rc=0)")
    if not falha and rc != 0:
        ERROS.append(f"{slug}: exemplo {nome} falhou (rc={rc}):\n{out[-1500:]}")
    mostrar = {k: v for k, v in arquivos.items() if not (k == "Cargo.toml" and "mostrar-toml" not in opts.get("_pos", []))}
    if "esconder-codigo" in opts.get("_pos", []):
        mostrar = {}
    cmds = cmd.split(" && ")
    return bloco_codigo(mostrar) + "\n" + term(f"~/projetos/{nome}", [(cmd, out)])

def b_terminal(opts, corpo, slug):
    nome = opts["_pos"][0]
    cwd = opts.get("cwd", f"~/projetos/{nome}")
    sec, ordem = secoes(corpo, "cmds")
    cmds = [l[2:] for l in sec[("cmds", "")].split("\n") if l.startswith("$ ")]
    preparo = None
    arquivos = {}
    for (k, r) in ordem:
        if k == "codigo": arquivos["src/main.rs"] = sec[(k, r)]
        elif k == "arquivo": arquivos[r.strip()] = sec[(k, r)]
    if arquivos or "projeto" in opts.get("_pos", []):
        preparo = arquivos
    saidas = rodar_terminal(nome, cmds, cwd, preparo)
    mostrar = {k: v for k, v in arquivos.items() if k != "Cargo.toml" or "mostrar-toml" in opts.get("_pos", [])}
    if "esconder-codigo" in opts.get("_pos", []):
        mostrar = {}
    return (bloco_codigo(mostrar) + "\n" if mostrar else "") + term(cwd, list(zip(cmds, saidas)))

def b_missao(opts, corpo, slug):
    global MISSOES
    MISSOES += 1
    goal = html.unescape(opts["goal"])
    cmd = opts.get("cmd", "cargo run")
    sec, ordem = secoes(corpo, "tarefa")
    tarefa = sec[("tarefa", "")]
    script = sec.get(("script", ""), "")
    sol = sec[("solucao", "")]
    rc, out = rodar_projeto("missao", {"src/main.rs": sol}, cmd)
    for meta in goal.split(";;"):
        meta = meta.strip()
        tipo, _, val = meta.partition(":")
        if tipo in ("out", "erro") and val not in out:
            ERROS.append(f"{slug}: missão {MISSOES}: '{val}' não está na saída real:\n{out}")
        if tipo == "outre" and not re.search(val, out, re.M):
            ERROS.append(f"{slug}: missão {MISSOES}: regex {val!r} não casa na saída real:\n{out}")
        if tipo == "src" and not re.search(val, sol, re.M):
            ERROS.append(f"{slug}: missão {MISSOES}: src {val!r} não casa na solução")
        if tipo == "semerro" and (re.search(r"^error(\[E\d+\])?:|panicked at", out, re.M)):
            ERROS.append(f"{slug}: missão {MISSOES}: semerro, mas a saída tem erro:\n{out}")
    datacmd = f' data-cmd="{attr(cmd)}"' if cmd != "cargo run" else ""
    return "\n".join([
        f'<div class="trycmd" data-goal="{attr(goal)}"{datacmd}>',
        f'<p class="try-task"><strong>Missão:</strong> {tarefa}</p>',
        f'<pre class="script" data-file="src/main.rs">\n{esc(script)}\n</pre>',
        f'<pre class="solucao" data-file="src/main.rs">\n{esc(sol)}\n</pre>',
        f'<pre class="saida-ok" data-file="src/main.rs" hidden>\n{esc(out)}\n</pre>',
        "</div>"])

MC_N = [0]
def b_mc(opts, corpo, slug):
    MC_N[0] += 1
    n = opts["_pos"][0]
    linhas = [l for l in corpo.split("\n") if l.strip()]
    q = linhas[0]
    ops = [l[2:] for l in linhas[1:] if l.startswith("- ")]
    nm = f"q{MC_N[0]}"
    return (f'<div class="mc" data-answer="{n}"><p class="mc-q">{q}</p>\n' +
            "\n".join(f'<label><input type="radio" name="{nm}"> {o}</label>' for o in ops) + "</div>")

EX_N = [0]
def b_ex(opts, corpo, slug):
    EX_N[0] += 1
    linhas = corpo.split("\n")
    enun = linhas[0]
    cod = "\n".join(linhas[1:]).strip("\n")
    def inp(m):
        return f'<input data-answer="{attr(m.group(1))}" aria-label="resposta">'
    partes = re.split(r"(\[\[[^\[\]]*\]\])", cod)
    h = ""
    for p in partes:
        if p.startswith("[[") and p.endswith("]]"):
            h += f'<input data-answer="{attr(p[2:-2])}" aria-label="resposta">'
        else:
            h += esc(p)
    return f'<div class="exercise"><h3>Exercício</h3><p>{enun}</p><div class="ex-code">{h}</div></div>'

BLOCOS = {"exemplo": b_exemplo, "terminal": b_terminal, "missao": b_missao, "mc": b_mc, "ex": b_ex}

def montar_aula(arq):
    txt = arq.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", txt, re.S)
    meta = {}
    for l in m.group(1).split("\n"):
        k, _, v = l.partition(":")
        meta[k.strip()] = v.strip()
    corpo = m.group(2)
    MC_N[0] = 0
    saida = []
    linhas = corpo.split("\n")
    i = 0
    while i < len(linhas):
        l = linhas[i]
        mb = re.match(r"^::: (\w+)\s*(.*)$", l)
        if mb:
            tipo, resto = mb.group(1), mb.group(2)
            j = i + 1
            while linhas[j] != ":::":
                j += 1
            saida.append(BLOCOS[tipo](parse_opts(resto), "\n".join(linhas[i + 1:j]), meta["slug"]))
            i = j + 1
            continue
        saida.append(l)
        i += 1
    return meta, "\n".join(saida)

PAGINA = '''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo}</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="assets/style.css">
<script>try{{var t=localStorage.getItem("tema");if(t)document.documentElement.setAttribute("data-theme",t)}}catch(e){{}}</script>
</head>
<body>
<div class="layout">
<nav class="sidebar" id="sidebar" aria-label="Tópicos"></nav>
<main class="main">
<div class="content">
{topo}
{corpo}

<div class="pager"></div>

</div>
</main>
</div>
<script src="assets/site.js"></script>
</body>
</html>
'''

def main():
    arqs = sorted(AULAS.glob("*.aula"))
    niveis = {}
    ordem_niveis = []
    paginas = []
    for a in arqs:
        meta, corpo = montar_aula(a) if (not SO or a.stem.split("-", 1)[1] in SO or True) else (None, None)
        paginas.append((meta, corpo))
        n = meta["nivel"]
        if n not in niveis:
            niveis[n] = []
            ordem_niveis.append(n)
        grupos = niveis[n]
        if not grupos or grupos[-1][0] != meta["grupo"]:
            grupos.append((meta["grupo"], []))
        grupos[-1][1].append((meta["slug"] + ".html", meta["menu"]))
    if ERROS:
        print("\n\n".join(ERROS))
        print(f"\n{len(ERROS)} erro(s); nada foi escrito.")
        sys.exit(1)
    for meta, corpo in paginas:
        if meta["slug"] == "index":
            topo = corpo
            corpo2 = ""
            html_ = PAGINA.format(titulo=esc(meta["titulo"]), desc=attr(meta["desc"]), topo="", corpo=corpo)
        else:
            topo = f'\n<div class="pager"></div>\n\n<h1>{meta["h1"]}</h1>\n'
            html_ = PAGINA.format(titulo=esc(meta["titulo"]), desc=attr(meta["desc"]), topo=topo, corpo=corpo)
        (ROOT / (meta["slug"] + ".html")).write_text(html_, encoding="utf-8")
    # NIVEIS no site.js
    js = "var NIVEIS = [\n"
    blocos = []
    for n in ordem_niveis:
        nome, curto, desc = NIVEL_NOME[n]
        gs = []
        for g, itens in niveis[n]:
            its = ",\n".join(f'      [{json.dumps(h)}, {json.dumps(t, ensure_ascii=False)}]' for h, t in itens)
            gs.append(f'    {{ grupo: {json.dumps(g, ensure_ascii=False)}, itens: [\n{its}\n    ]}}')
        blocos.append(f'  {{ id: "{n}", nome: "{nome}", curto: "{curto}", desc: "{desc}", grupos: [\n' + ",\n".join(gs) + "\n  ]}")
    js += ",\n".join(blocos) + "\n];"
    site = (ROOT / "assets" / "site.js").read_text(encoding="utf-8")
    site = re.sub(r"/\* niveis:inicio \*/.*?/\* niveis:fim \*/", lambda m: "/* niveis:inicio */\n" + js + "\n/* niveis:fim */", site, flags=re.S)
    (ROOT / "assets" / "site.js").write_text(site, encoding="utf-8")
    print(f"{len(paginas)} página(s), {MISSOES} missão(ões).")

if __name__ == "__main__":
    main()
