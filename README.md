# Guia Rust

Site: https://wallysondevs.github.io/guia-rust/

Curso de Rust em português, feito para quem **está começando**. Funciona como uma escola: uma aula para cada assunto, organizadas em **3 níveis** (43 páginas). O curso começa no `cargo`, em variáveis e tipos, passa por ownership, borrowing, structs, enums, traits, generics, lifetimes, closures, iteradores, testes, concorrência e macros, e termina num projeto final.

- **Nível 1 · Iniciante** (16 páginas): começando, fundamentos, ownership, structs e enums.
- **Nível 2 · Intermediário** (15 páginas): tratando erros, coleções, organizando o código, abstração e qualidade.
- **Nível 3 · Avançado** (12 páginas): smart pointers, concorrência, Rust avançado e o projeto final (uma ferramenta de linha de comando em duas partes).

Cada aula explica o código parte por parte, mostra a saída real e o que acontece quando dá errado, com a mensagem verdadeira do compilador. No fim vêm exercícios e perguntas de múltipla escolha. **Todo exemplo foi compilado e rodado de verdade** com o **rustc 1.100.0** e o **cargo 1.100.0** (edição 2024). Os projetos dos exemplos ficam na pasta fictícia `/home/ana/projetos`, com o terminal `ana@notebook`.

Nos exemplos com threads, a ordem das linhas muda a cada execução, porque quem decide qual thread roda é o sistema operacional. A saída mostrada é de uma execução real, e a aula avisa quando isso acontece.

Para praticar, as páginas trazem **112 missões** no modo **"Rode no seu terminal"** (`.trycmd`). Não há simulador: você usa o seu próprio Rust.

1. Leia a missão e clique em **Copiar código**.
2. Rode no seu terminal com `cargo run` (ou o comando que a missão pedir, como `cargo test`).
3. Cole a saída na caixa e clique em **Conferir**: a caixa diz se você chegou ao resultado pedido.
4. Depois do primeiro **Conferir**, o botão **Ver solução** é liberado.

A caixa é montada por `assets/rode-local.js`. O código e a saída colada ficam só na página: nada é enviado nem guardado no navegador.

Site 100% estático (HTML + CSS + JS, sem build e sem dependências externas): abre direto no navegador e funciona no GitHub Pages. As páginas `.html` são geradas a partir de `aulas/*.aula` pelo `tools/montar.py`, mas já vêm prontas no repositório.

## Estrutura

```
index.html                 página inicial
<tema>.html                uma aula por tema (geradas a partir de aulas/)
aulas/*.aula               o texto-fonte de cada aula (exemplos, terminais, missões, exercícios)
assets/style.css           visual
assets/site.js             níveis/menu (lista NIVEIS, gerada pelo montador), Anterior/Próximo, exercícios
assets/rode-local.js       a caixa "Rode no seu terminal" (.trycmd)
assets/rode-local.css      visual da caixa
tools/montar.py            monta as páginas: compila e roda cada exemplo de verdade com o cargo
tools/testar-missoes.js    testa as missões e compila e roda cada solução com o cargo
tools/testar-navegador.js  abre as páginas num Chrome sem janela e confere as caixas
tools/checar-privacidade.sh  procura dados de máquina real nas páginas e no histórico
.nojekyll                  faz o GitHub Pages servir os arquivos como estão
```

## Testes

```bash
python3 tools/montar.py                      # monta todas as páginas (usa o cache dos exemplos já rodados)
python3 tools/montar.py --sem-cache threads  # remonta só esta aula, rodando tudo de novo
node tools/testar-missoes.js                 # todas as missões, compilando e rodando cada solução (precisa do cargo)
node tools/testar-missoes.js --sem-compilar  # só a estrutura das caixas e as metas do código
node tools/testar-missoes.js --secao "Começando"   # só uma seção do menu
node tools/testar-navegador.js --todas       # todas as páginas num Chrome sem janela (precisa do puppeteer-core em tools/node_modules)
bash tools/checar-privacidade.sh             # privacidade: rode antes de todo commit
```

## Publicar no GitHub Pages

Envie a pasta para um repositório e ative **Settings → Pages → Deploy from a branch → main / (root)**.

## Adicionar uma aula

Escreva a aula em `aulas/NN-tema.aula` (copie uma existente como modelo; o formato está no começo de `tools/montar.py`) e rode `python3 tools/montar.py`: ele gera o `.html` e inclui a página na lista `NIVEIS` de `assets/site.js`. Depois rode `node tools/testar-missoes.js` e `bash tools/checar-privacidade.sh`.
