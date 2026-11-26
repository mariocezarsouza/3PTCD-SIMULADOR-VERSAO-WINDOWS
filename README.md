# Simulador Inteligente de Armazenagem – UCE II
### Versão Desktop para Windows · v4.6.0

Aplicação desktop **nativa para Windows** que calcula quanto um armazém perde com **avarias de embalagens** e compara soluções de proteção — **cantoneiras V-Board, estantes de aço e divisórias modulares** — por economia líquida, ROI, payback e custo-benefício. Funciona **sem internet e sem navegador**.

Projeto acadêmico da **UCE II** — **Faculdade SENAI Contagem** — turma **3º PTCD**.

![Python](https://img.shields.io/badge/Python-3.10–3.13-3776AB?logo=python&logoColor=white)
![Tkinter](https://img.shields.io/badge/GUI-Tkinter-2C5D8F)
![matplotlib](https://img.shields.io/badge/Gráficos-matplotlib-11557C)
![SQLite](https://img.shields.io/badge/SQLite-DB-003B57?logo=sqlite&logoColor=white)
![Windows](https://img.shields.io/badge/plataforma-Windows-0078D6?logo=windows&logoColor=white)
![Versão](https://img.shields.io/badge/versão-4.6.0-E65100)
![Licença](https://img.shields.io/badge/licença-MIT-green)

---

## Sumário
- [Equipe](#equipe)
- [O problema](#o-problema)
- [Funcionalidades](#funcionalidades)
- [Abas do programa](#abas-do-programa)
- [Modelo de cálculo](#modelo-de-cálculo)
- [Central de relatórios](#central-de-relatórios)
- [Biblioteca de documentos](#biblioteca-de-documentos)
- [Instalação (usuário final)](#instalação-usuário-final)
- [Onde ficam os dados](#onde-ficam-os-dados)
- [Para desenvolvedores](#para-desenvolvedores)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Tecnologias](#tecnologias)
- [Histórico de versões](#histórico-de-versões)
- [Licença](#licença)

---

## Equipe

| Item | Descrição |
|---|---|
| **Instituição** | Faculdade SENAI Contagem – SENAI-MG |
| **Projeto** | UCE II – Simulador de armazenagem |
| **Turma** | 3º PTCD |
| **Equipe** | Daniel · Felipe · Marcos · Mário |
| **Orientadora** | Profa. Dra. Michele Cândida Carvalho de Oliveira |

## O problema

Em muitos armazéns, caixas empilhadas sem proteção amassam, perdem as quinas ou deslizam durante a movimentação. Cada caixa danificada vira prejuízo. O simulador responde a duas perguntas práticas:

1. **Quanto o armazém perde por mês e no período com avarias?**
2. **Qual proteção compensa mais** — e em quanto tempo ela se paga?

## Funcionalidades
- **Cálculo automático ao digitar**, com campos inválidos destacados e avisos inteligentes (empilhamento limitado pelo pé-direito, caixa que não cabe, solução que não se paga etc.).
- **Três soluções de proteção** configuráveis (valor, quantidade, redução de danos e vida útil), que podem ser incluídas ou excluídas da análise.
- **Quatro critérios de recomendação** escolhidos pelo usuário.
- **Dashboard** com 6 indicadores e **8 gráficos** de análise, incluindo evolução mensal acumulada e **análise de sensibilidade (±20%)**.
- **Central de relatórios** em PDF (A4, com logo, numeração e nome do cenário) e **impressão direta**.
- **Exportação** em PDF, CSV (compatível com Excel em português), JSON e PNG.
- **Biblioteca de documentos** ilimitada, com banco SQLite.
- **Cenários** salvos e reabertos automaticamente; compatível com cenários das versões 4.x e do simulador HTML 2.x.
- Interface ajustada a telas pequenas (1366×768) e a escalas de DPI do Windows; erros registrados em log.

## Abas do programa

| Aba | Conteúdo |
|---|---|
| **01 Dados** | Armazém, caixa, avarias, horizonte, soluções e critério de recomendação |
| **02 Dashboard** | 6 indicadores e avisos automáticos |
| **03 Comparativo** | Fichas das soluções e tabela analítica ordenada pelo critério |
| **04 Análise** | 8 gráficos (os mesmos do PDF) |
| **05 Relatório** | Central de relatórios + resultado técnico completo |
| **06 Documentos** | Acesso rápido aos 3 documentos principais + biblioteca de documentos |

## Modelo de cálculo

**Parâmetros de entrada (valores padrão):**

| Grupo | Parâmetro | Padrão |
|---|---|---|
| Armazém | Área total do piso | 9 m² |
| Armazém | Fator de ocupação | 80% |
| Armazém | Empilhamento máximo | 5 camadas |
| Armazém | Pé-direito útil (0 = sem limite) | 1,2 m |
| Caixa | Largura × comprimento × altura | 0,30 × 0,40 × 0,20 m |
| Avarias | Valor por caixa danificada | R$ 25,00 |
| Avarias | Taxa de avaria sem proteção | 10% das caixas/mês |
| Avarias | Horizonte de análise | 12 meses (1 a 240) |

**Soluções (valores padrão, editáveis):**

| Solução | Valor unitário | Quantidade | Redução de danos | Vida útil |
|---|---:|---:|:---:|:---:|
| Cantoneiras V-Board | R$ 1,50 | 4 por caixa | 75% | 6 meses |
| Estantes de aço | R$ 250,00 | 6 | 90% | 120 meses |
| Divisórias modulares | R$ 120,00 | 8 | 85% | 60 meses |

**Fórmulas:**

```
área útil          = área do piso × fator de ocupação
caixas por camada  = ⌊ área útil ÷ (largura × comprimento) ⌋
camadas            = mín( empilhamento máximo , ⌊ pé-direito ÷ altura da caixa ⌋ )
caixas armazenadas = caixas por camada × camadas

avarias por mês    = caixas armazenadas × taxa de avaria
perda mensal       = avarias por mês × valor por caixa
perda no horizonte = perda mensal × horizonte (meses)

para cada solução incluída:
  quantidade          = qtd. por caixa × caixas (cantoneiras) ou quantidade informada
  investimento        = quantidade × valor unitário
  recompras (ciclos)  = ⌈ horizonte ÷ vida útil ⌉
  custo no horizonte  = investimento × recompras
  perda evitada       = perda no horizonte × redução de danos
  perda residual      = perda no horizonte − perda evitada
  economia líquida    = perda evitada − custo no horizonte
  ROI (%)             = economia líquida ÷ custo no horizonte × 100
  custo por 1% de proteção = custo no horizonte ÷ redução (%)
  payback (meses)     = investimento ÷ (perda mensal × redução)
                        (sem retorno se for maior que a vida útil)
```

**Critérios de recomendação:**

| Critério | Escolhe a solução com… |
|---|---|
| Economia líquida *(padrão)* | maior economia líquida no horizonte |
| ROI | maior retorno sobre o investimento |
| Payback | menor tempo de retorno |
| Custo-benefício | menor custo por 1% de proteção |

Quando o critério escolhido diverge da melhor economia líquida, o programa avisa qual seria a opção mais econômica.

## Central de relatórios

Na aba **05 Relatório**, marque os relatórios e escolha:
- **Gerar PDF dos selecionados** (um único arquivo);
- **Imprimir selecionados** (impressora padrão do Windows);
- **Gerar um PDF por relatório**;
- **Exportar pacote completo:** PDF completo + 8 PDFs separados + CSV + JSON + 8 gráficos PNG.

| Nº | Relatório |
|:---:|---|
| 1 | Resumo do cenário e parâmetros |
| 2 | Comparativo das soluções e leitura do resultado |
| 3 | Gráficos: custo × perda evitada e economia líquida |
| 4 | Gráficos: custo por 1% de proteção e perda residual |
| 5 | Gráficos: payback e análise multicritério |
| 6 | Evolução mensal acumulada e sensibilidade (±20%) |
| 7 | Ficha detalhada de cada solução |
| 8 | Lista de documentos do projeto |

A impressão direta usa o leitor de PDF padrão do Windows. Se nenhum estiver configurado, o PDF abre para imprimir com `Ctrl+P`.

## Biblioteca de documentos

Na aba **06 Documentos**:
- **Acesso rápido** ao Mapa de Empatia, ao Business Model Canvas e à Pesquisa de Anterioridade do projeto.
- **Adicionar documentos:** vários arquivos de uma vez (PDF, Word, Excel, PowerPoint, imagens, texto), sem limite de quantidade.
- **Abrir** (ou duplo clique), **Imprimir**, **Editar dados** (título, categoria, observações), **Substituir arquivo**, **Remover**, **Abrir pasta** e **Buscar**.
- O programa guarda uma cópia de cada arquivo; o original não é alterado.

## Instalação (usuário final)

1. Execute `Setup_Simulador_Armazenagem_UCE_II_Desktop_v4.6.0.exe` (gerado na pasta `installer_output`).
2. Avance as telas. **Não é preciso ser administrador** (há opção de instalar para todos os usuários).
3. Abra pelo menu Iniciar: **"Simulador Inteligente de Armazenagem - UCE II"**.

- Se já houver uma versão 4.x instalada, o Setup atualiza por cima.
- Se o **Windows SmartScreen** avisar "aplicativo não reconhecido", clique em **Mais informações › Executar assim mesmo** — o instalador não é assinado digitalmente, o que é normal em projetos acadêmicos.

> O instalador não fica versionado neste repositório: ele é gerado pelo `GERAR_INSTALADOR.bat` (veja [Para desenvolvedores](#para-desenvolvedores)).

## Onde ficam os dados

```
%LOCALAPPDATA%\SimuladorArmazenagemUCEII\
├── relatorios\                  cópias dos documentos do trabalho
├── simulador_armazenagem.db     banco SQLite da biblioteca de documentos
├── ultimo_cenario.json          último cenário calculado (reabre sozinho)
└── simulador.log                registro de erros
```

- Há um atalho **"Pasta de dados e documentos"** no menu Iniciar.
- **Desinstalar o programa não apaga essa pasta.**
- Documentos da versão 4.5.x (pasta `relatorios` ao lado do programa) são copiados automaticamente na primeira abertura.

## Para desenvolvedores

**Pré-requisitos:** Python **3.10 a 3.13** e **Inno Setup 6** ([jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php)).

**Gerar o programa e o instalador:** dê dois cliques em `GERAR_INSTALADOR.bat`. Ele:
1. cria um ambiente virtual isolado;
2. instala as versões fixadas em `requirements.txt`;
3. gera o programa em `dist\` com PyInstaller (modo pasta, `--onedir`, que abre mais rápido e é menos bloqueado por antivírus);
4. roda o autoteste do programa gerado;
5. compila o instalador com o Inno Setup (`installer.iss`).

**Executar e testar sem gerar o instalador:**

```bash
pip install -r requirements.txt
python simulador_desktop.py                    # abre o programa
python simulador_desktop.py --selftest PASTA   # gera PDF/CSV/JSON/PNG na PASTA e fecha
```

**Dependências (`requirements.txt`):** `matplotlib`, `numpy`, `pillow` e `pyinstaller` (versões fixadas).

## Estrutura do repositório

```
3PTCD-SIMULADOR-VERSAO-WINDOWS/
├── simulador_desktop.py                  # Aplicação (Tkinter + matplotlib + SQLite)
├── build_windows.py                      # Build com PyInstaller + autoteste
├── Simulador_Armazenagem_UCE_II.spec     # Especificação do PyInstaller
├── installer.iss                         # Script do instalador (Inno Setup)
├── GERAR_INSTALADOR.bat                  # Gera programa + instalador com um clique
├── requirements.txt                      # Dependências com versões fixadas
├── simulador.ico                         # Ícone do programa
├── logo_simulador.jpg / logo_72.png      # Logos (interface e PDF)
├── LEIA-ME.txt                           # Instruções em texto simples
├── CHANGELOG.txt                         # Histórico de versões
├── Licença MIT                           # Licença
└── README.md                             # Este arquivo
```

## Tecnologias
- **Python 3** — linguagem principal
- **Tkinter / ttk** — interface gráfica nativa
- **matplotlib** e **NumPy** — gráficos e relatórios em PDF (`PdfPages`)
- **SQLite3** — biblioteca de documentos
- **Pillow** — imagens e logos
- **PyInstaller** — empacotamento do executável
- **Inno Setup 6** — instalador para Windows

## Histórico de versões

### v4.6.0 (atual)
- **Relatórios:** central com 8 relatórios selecionáveis (PDF único, um PDF por relatório ou impressão direta); novos relatórios de evolução mensal, sensibilidade (tornado ±20%), ficha de cada solução e lista de documentos; aba Análise com os 8 gráficos; PDF sempre em A4 com logo.
- **Documentos:** biblioteca sem limite, com categoria, observações, busca e ações de arquivo; dados movidos para `%LOCALAPPDATA%` com migração automática.
- **Modelo de cálculo** alinhado ao simulador HTML v2.1: taxa de avaria mensal, horizonte e vida útil com recompras, payback em meses, fator de ocupação, limite pelo pé-direito e critério escolhido pelo usuário; correções de arredondamento.
- **Interface:** logo no cabeçalho, recálculo automático, roda do mouse corrigida, ajuste a telas pequenas e DPI, último cenário reaberto e log de erros.
- **Exportações:** CSV com vírgula decimal; compatibilidade com cenários 4.x e HTML 2.x.
- **Empacotamento:** modo pasta (`--onedir`), versões fixadas, build isolado com autoteste e instalador com atualização sobre 4.x.

Detalhes completos em [`CHANGELOG.txt`](CHANGELOG.txt).

## Licença

Distribuído sob a **Licença MIT** — veja o arquivo [`Licença MIT`](<Licença MIT>).

---

<sub>Projeto acadêmico UCE II — Faculdade SENAI Contagem · 3º PTCD · Equipe: Daniel, Felipe, Marcos e Mário · Orientadora: Profa. Dra. Michele Cândida Carvalho de Oliveira.</sub>
