"""Simulador Inteligente de Armazenagem – UCE II (desktop Windows).

Aplicação Tkinter + matplotlib. Modelo de cálculo alinhado ao simulador HTML v2.1:
taxa de avaria, horizonte de análise, vida útil das soluções, payback em meses e
critério de decisão escolhido pelo usuário.

Uso:
    python simulador_desktop.py              abre o programa
    python simulador_desktop.py --selftest D gera PDF/CSV/JSON/PNG na pasta D e fecha
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from datetime import datetime
import csv, json, logging, math, os, re, shutil, sqlite3, subprocess, sys, textwrap, traceback, unicodedata

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle, FancyBboxPatch
from matplotlib.ticker import FuncFormatter
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

VERSION = "4.6.0"
APP_TITLE = f"Simulador Inteligente de Armazenagem – UCE II  (v{VERSION})"
APP_DIR_NAME = "SimuladorArmazenagemUCEII"
EPS = 1e-9
EQUIPE = "Daniel · Felipe · Marcos · Mário"
ORIENTADORA = "Profa. Dra. Michele Cândida Carvalho de Oliveira"

NAVY = "#002855"; BLUE = "#185FA5"; ORANGE = "#E65100"; BG = "#F4F7FB"; WHITE = "#FFFFFF"
INK = "#172033"; MUTED = "#566173"; GREEN = "#1D7A46"; RED = "#B42318"; AMBER = "#8A4F00"; LINE = "#DCE3EC"
PALE_BLUE = "#EAF3FC"; PALE_ORANGE = "#FFF1E8"; PALE_GREEN = "#EAF6EE"; PALE_RED = "#FFF0EF"

# ===== Parâmetros =====
# key, rótulo, unidade, padrão, mínimo, mínimo exclusivo, máximo, inteiro, grupo
FIELDS = [
    ("area", "Área total do piso", "m²", 9, 0, True, None, False, "armazem"),
    ("ocup", "Fator de ocupação", "%", 80, 0, True, 100, False, "armazem"),
    ("pilha", "Empilhamento máximo", "camadas", 5, 1, False, None, True, "armazem"),
    ("pe", "Pé-direito útil (0 = sem limite)", "m", 1.2, 0, False, None, False, "armazem"),
    ("larg", "Largura da caixa", "m", 0.30, 0, True, None, False, "caixa"),
    ("comp", "Comprimento da caixa", "m", 0.40, 0, True, None, False, "caixa"),
    ("alt", "Altura da caixa", "m", 0.20, 0, True, None, False, "caixa"),
    ("vperd", "Valor por caixa danificada", "R$", 25, 0, True, None, False, "avaria"),
    ("taxa", "Taxa de avaria sem proteção", "% das caixas/mês", 10, 0, True, 100, False, "avaria"),
    ("horiz", "Horizonte de análise", "meses", 12, 1, False, 240, True, "avaria"),
]
SOLS = [
    {"k": "cant", "nome": "Cantoneiras V-Board", "curto": "Cantoneiras\nV-Board", "por_caixa": True, "def": (1.5, 4, 75, 6)},
    {"k": "est", "nome": "Estantes de aço", "curto": "Estantes\nde aço", "por_caixa": False, "def": (250, 6, 90, 120)},
    {"k": "div", "nome": "Divisórias modulares", "curto": "Divisórias\nmodulares", "por_caixa": False, "def": (120, 8, 85, 60)},
]
for _s in SOLS:
    _k = _s["k"]
    FIELDS += [
        ("v_" + _k, "Valor unitário", "R$", _s["def"][0], 0, False, None, False, _k),
        ("q_" + _k, "Qtd. por caixa" if _s["por_caixa"] else "Quantidade", "un.", _s["def"][1], 0, False, None, True, _k),
        ("r_" + _k, "Redução de danos", "%", _s["def"][2], 0, False, 100, False, _k),
        ("l_" + _k, "Vida útil", "meses", _s["def"][3], 1, False, None, True, _k),
    ]
FIELD_BY_KEY = {f[0]: f for f in FIELDS}

CRITERIOS = {
    "econ": ("Maior economia líquida no horizonte", lambda o: o["econ"]),
    "roi": ("Maior ROI", lambda o: o["roi"] if o["roi"] is not None else (math.inf if o["evitada"] > 0 else -math.inf)),
    "payback": ("Menor payback", lambda o: -o["payback"]),
    "cb": ("Menor custo por 1% de proteção", lambda o: -o["cb"]),
}
DEFAULTS = {f[0]: f[3] for f in FIELDS}
DEFAULTS.update({"on_" + s["k"]: True for s in SOLS})
DEFAULTS["criterio"] = "econ"


# ===== Formatação =====
def _br(v, d=2):
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def nfmt(v, d=2):
    return _br(v, d)

def brl(v):
    return ("- " if v < 0 else "") + "R$ " + _br(abs(v))

def brl_pdf(v):
    """Moeda para textos do matplotlib: '$' escapado para não virar fórmula."""
    return brl(v).replace("$", r"\$")

def compacto(v):
    a = abs(v)
    if a >= 1e6:
        s = _br(v / 1e6, 1) + " mi"
    elif a >= 1e3:
        s = _br(v / 1e3, 1) + " mil"
    else:
        s = _br(v, 0)
    return s

def eixo_brl(v, _pos=None):
    return r"R\$ " + compacto(v)

def pct(v, d=1):
    return "—" if v is None else _br(v, d) + "%"

def fmt_payback(v):
    if v == 0:
        return "imediato"
    return _br(v, 1) + " meses" if math.isfinite(v) else "não se paga"

def fmt_cb(v):
    return brl(v) if math.isfinite(v) else "—"

def dec(v):
    """Número para CSV do Excel em português: vírgula decimal, 2 casas."""
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return ""
    return f"{v:.2f}".replace(".", ",")


# ===== Pastas e arquivos =====
def resource_path(name):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name

def legacy_dir():
    """Pasta onde as versões até 4.5.3 guardavam banco e relatórios (ao lado do programa)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

def data_dir():
    """Dados do usuário ficam em %LOCALAPPDATA%: graváveis mesmo com o programa em Arquivos de Programas."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    d = Path(base) / APP_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d

def reports_dir():
    d = data_dir() / "relatorios"
    d.mkdir(parents=True, exist_ok=True)
    return d

def database_path():
    return data_dir() / "simulador_armazenagem.db"

def last_scenario_path():
    return data_dir() / "ultimo_cenario.json"

def open_path(p):
    p = str(p)
    if sys.platform.startswith("win"):
        os.startfile(p)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])


# ===== Biblioteca de documentos do trabalho (SQLite + pasta relatorios) =====
# Os três documentos fixos têm acesso rápido; qualquer número de outros documentos pode ser adicionado.
DOCUMENTOS_FIXOS = {
    "mapa_empatia": ("Mapa de Empatia", "mapa_empatia.pdf"),
    "business_model_canvas": ("Business Model Canvas", "business_model_canvas.pdf"),
    "pesquisa_anterioridade": ("Pesquisa de Anterioridade", "pesquisa_anterioridade.pdf"),
}
CATEGORIAS = ["Documento do trabalho", "Mapa de Empatia", "Business Model Canvas", "Pesquisa de Anterioridade",
              "Relatório técnico", "Apresentação", "Planilha", "Ata de reunião", "Pesquisa de campo", "Cronograma",
              "Imagem / foto", "Outro"]
TIPOS_ARQUIVO = [("Documentos do trabalho", "*.pdf *.docx *.doc *.xlsx *.xls *.pptx *.ppt *.odt *.ods *.odp *.txt *.csv *.png *.jpg *.jpeg"),
                 ("Todos os arquivos", "*.*")]

def categoria_por_extensao(ext):
    ext = ext.lower()
    if ext in (".ppt", ".pptx", ".odp"):
        return "Apresentação"
    if ext in (".xls", ".xlsx", ".ods", ".csv"):
        return "Planilha"
    if ext in (".png", ".jpg", ".jpeg"):
        return "Imagem / foto"
    return "Documento do trabalho"

def tamanho_legivel(n):
    if not n:
        return "—"
    for unidade in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidade == "GB":
            return (f"{n:.0f} {unidade}" if unidade == "B" else _br(n, 1) + f" {unidade}")
        n /= 1024

def _db():
    con = sqlite3.connect(database_path())
    con.row_factory = sqlite3.Row
    return con

def migrate_legacy_reports():
    """Copia relatórios das versões até 4.5.3, que ficavam ao lado do programa."""
    old = legacy_dir() / "relatorios"
    if not old.is_dir() or old.resolve() == reports_dir().resolve():
        return
    for _titulo, arquivo in DOCUMENTOS_FIXOS.values():
        src, dst = old / arquivo, reports_dir() / arquivo
        if src.exists() and not dst.exists():
            try:
                shutil.copy2(src, dst)
                logging.info("Relatório migrado: %s", src)
            except OSError:
                logging.exception("Falha ao migrar %s", src)

def init_document_database():
    con = _db()
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS documentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT UNIQUE,
                titulo TEXT NOT NULL,
                categoria TEXT NOT NULL DEFAULT 'Documento do trabalho',
                arquivo TEXT,
                nome_original TEXT,
                tamanho INTEGER,
                observacoes TEXT DEFAULT '',
                criado_em TEXT DEFAULT (datetime('now','localtime')),
                atualizado_em TEXT DEFAULT (datetime('now','localtime'))
            )""")
        for tipo, (titulo, arquivo) in DOCUMENTOS_FIXOS.items():
            con.execute("INSERT OR IGNORE INTO documentos (tipo,titulo,categoria) VALUES (?,?,?)", (tipo, titulo, titulo))
            p = reports_dir() / arquivo
            if p.exists():
                con.execute("UPDATE documentos SET arquivo=?, nome_original=COALESCE(nome_original,?), tamanho=? "
                            "WHERE tipo=? AND arquivo IS NULL", (arquivo, arquivo, p.stat().st_size, tipo))
        con.commit()
    finally:
        con.close()

def listar_documentos(filtro=""):
    con = _db()
    try:
        sql = "SELECT * FROM documentos"
        args = ()
        if filtro.strip():
            sql += " WHERE titulo LIKE ? OR categoria LIKE ? OR nome_original LIKE ? OR observacoes LIKE ?"
            args = tuple(f"%{filtro.strip()}%" for _ in range(4))
        sql += " ORDER BY tipo IS NULL, id"
        return [dict(r) for r in con.execute(sql, args).fetchall()]
    finally:
        con.close()

def obter_documento(doc_id=None, tipo=None):
    con = _db()
    try:
        if tipo:
            row = con.execute("SELECT * FROM documentos WHERE tipo=?", (tipo,)).fetchone()
        else:
            row = con.execute("SELECT * FROM documentos WHERE id=?", (doc_id,)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()

def caminho_documento(doc):
    return reports_dir() / doc["arquivo"] if doc and doc.get("arquivo") else None

def _nome_destino(doc_id, tipo, origem):
    ext = origem.suffix.lower()
    if tipo and ext == ".pdf":
        return DOCUMENTOS_FIXOS[tipo][1]
    base = tipo or f"{doc_id:04d}_{safe_name(origem.stem).replace(' ', '_')}"
    return base + ext

def adicionar_documento(origem, titulo=None, categoria=None):
    origem = Path(origem)
    con = _db()
    try:
        cur = con.execute("INSERT INTO documentos (titulo,categoria,nome_original) VALUES (?,?,?)",
                          (titulo or origem.stem, categoria or categoria_por_extensao(origem.suffix), origem.name))
        doc_id = cur.lastrowid
        destino = reports_dir() / _nome_destino(doc_id, None, origem)
        try:
            shutil.copy2(origem, destino)
        except OSError:
            con.rollback()
            raise
        con.execute("UPDATE documentos SET arquivo=?, tamanho=? WHERE id=?", (destino.name, destino.stat().st_size, doc_id))
        con.commit()
        return doc_id
    finally:
        con.close()

def substituir_arquivo(doc_id, origem):
    origem = Path(origem)
    doc = obter_documento(doc_id)
    antigo = caminho_documento(doc)
    destino = reports_dir() / _nome_destino(doc_id, doc["tipo"], origem)
    if origem.resolve() != destino.resolve():
        shutil.copy2(origem, destino)
    if antigo and antigo.exists() and antigo.resolve() != destino.resolve():
        antigo.unlink()
    con = _db()
    try:
        con.execute("UPDATE documentos SET arquivo=?, nome_original=?, tamanho=?, atualizado_em=datetime('now','localtime') "
                    "WHERE id=?", (destino.name, origem.name, destino.stat().st_size, doc_id))
        con.commit()
    finally:
        con.close()

def atualizar_documento(doc_id, titulo, categoria, observacoes):
    con = _db()
    try:
        con.execute("UPDATE documentos SET titulo=?, categoria=?, observacoes=?, atualizado_em=datetime('now','localtime') "
                    "WHERE id=?", (titulo, categoria, observacoes, doc_id))
        con.commit()
    finally:
        con.close()

def remover_documento(doc_id):
    doc = obter_documento(doc_id)
    if not doc:
        return
    p = caminho_documento(doc)
    if p and p.exists():
        p.unlink()
    con = _db()
    try:
        if doc["tipo"]:   # documento fixo: mantém o atalho, só esvazia
            con.execute("UPDATE documentos SET arquivo=NULL, nome_original=NULL, tamanho=NULL, "
                        "atualizado_em=datetime('now','localtime') WHERE id=?", (doc_id,))
        else:
            con.execute("DELETE FROM documentos WHERE id=?", (doc_id,))
        con.commit()
    finally:
        con.close()

def imprimir_arquivo(path):
    """Envia o arquivo à impressora padrão pelo programa associado do Windows."""
    if sys.platform.startswith("win"):
        os.startfile(str(path), "print")
    else:
        subprocess.Popen(["lp", str(path)])


# ===== Modelo (sem interface) =====
def modelo(v):
    area_cx = v["larg"] * v["comp"]
    area_util = v["area"] * v["ocup"] / 100
    por_camada = math.floor(area_util / area_cx + EPS)
    cam_pe = math.floor(v["pe"] / v["alt"] + EPS) if v["pe"] > 0 else math.inf
    camadas = int(min(v["pilha"], cam_pe))
    total = por_camada * camadas
    avarias_mes = total * v["taxa"] / 100
    perda_mes = avarias_mes * v["vperd"]
    perda_h = perda_mes * v["horiz"]
    opts = []
    for s in SOLS:
        k = s["k"]
        if not v["on_" + k]:
            continue
        q = v["q_" + k]
        qtd = total * q if s["por_caixa"] else q
        inv = qtd * v["v_" + k]
        vida = v["l_" + k]
        ciclos = math.ceil(v["horiz"] / vida - EPS)
        custo_h = inv * ciclos
        r = v["r_" + k] / 100
        evitada = perda_h * r
        econ = evitada - custo_h
        ganho_mes = perda_mes * r
        payback = 0.0 if inv == 0 else (inv / ganho_mes if ganho_mes > 0 else math.inf)
        if payback > vida:
            payback = math.inf
        opts.append({
            "k": k, "nome": s["nome"], "curto": s["curto"], "qtd": qtd, "inv": inv, "vida": vida, "ciclos": ciclos,
            "custo_h": custo_h, "r": r, "evitada": evitada, "residual": perda_h - evitada, "econ": econ,
            "roi": econ / custo_h * 100 if custo_h > 0 else None,
            "cb": custo_h / (r * 100) if r > 0 else math.inf, "payback": payback,
        })
    score = CRITERIOS.get(v["criterio"], CRITERIOS["econ"])[1]
    ranked = sorted(opts, key=lambda o: (score(o), o["econ"]), reverse=True)
    for i, o in enumerate(ranked, 1):
        o["rank"] = i
    best = ranked[0] if ranked else None
    best_econ = max(opts, key=lambda o: o["econ"]) if opts else None
    return {
        "v": v, "area_cx": area_cx, "area_util": area_util, "por_camada": por_camada, "cam_pe": cam_pe,
        "camadas": camadas, "lim_pe": cam_pe < v["pilha"], "total": total, "volume": v["larg"] * v["comp"] * v["alt"],
        "avarias_mes": avarias_mes, "perda_mes": perda_mes, "perda_h": perda_h,
        "opts": opts, "ranked": ranked, "best": best, "best_econ": best_econ,
        "data": datetime.now(),
    }

def alertas(r):
    v, a = r["v"], []
    if r["por_camada"] == 0:
        a.append(("bad", "Nenhuma caixa cabe na área útil informada (área × ocupação é menor que a base da caixa)."))
    elif r["camadas"] == 0:
        a.append(("bad", f"A altura da caixa ({nfmt(v['alt'])} m) é maior que o pé-direito útil ({nfmt(v['pe'])} m)."))
    elif r["lim_pe"]:
        a.append(("warn", f"O empilhamento foi limitado a {r['camadas']} camada(s) pelo pé-direito, abaixo das {int(v['pilha'])} informadas."))
    b = r["best"]
    if not b:
        a.append(("bad", "Nenhuma solução está incluída. Marque “Incluir” em pelo menos uma solução."))
        return a
    if b["econ"] <= 0:
        a.append(("bad", f"A solução recomendada não se paga em {int(v['horiz'])} meses (economia líquida de {brl(b['econ'])}). "
                         "Nesse cenário, investir não compensa."))
    be = r["best_econ"]
    if be is not b:
        a.append(("info", f"Pelo critério de economia líquida, a melhor opção seria {be['nome']} ({brl(be['econ'])})."))
    if r["total"] > 0:
        for o in r["opts"]:
            if o["inv"] == 0:
                a.append(("warn", f"{o['nome']} tem investimento zero (quantidade ou valor unitário igual a 0)."))
    return a


# ===== Gráficos (usados na tela e no PDF) =====
def _sem_dados(ax, r):
    if r["opts"]:
        return False
    ax.text(.5, .5, "Nenhuma solução incluída", ha="center", va="center", transform=ax.transAxes, color=MUTED)
    ax.set_xticks([]); ax.set_yticks([])
    return True

def _estilo(ax, titulo, ylabel, moeda=False):
    ax.set_title(titulo, fontsize=12, fontweight="bold", color=NAVY, pad=10)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.grid(axis="y", alpha=.2)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8.5)
    if moeda:
        ax.yaxis.set_major_formatter(FuncFormatter(eixo_brl))

def _rotulos(ax, bars, vals, fmt):
    for b, v in zip(bars, vals):
        ax.annotate(fmt(v), (b.get_x() + b.get_width() / 2, b.get_height() if v >= 0 else b.get_y()),
                    xytext=(0, 3 if v >= 0 else -3), textcoords="offset points",
                    ha="center", va="bottom" if v >= 0 else "top", fontsize=7.5, color=INK)

def chart_custo_evitada(ax, r):
    ax.clear()
    if _sem_dados(ax, r):
        return
    o = r["opts"]; x = np.arange(len(o)); w = .36
    b1 = ax.bar(x - w / 2, [s["custo_h"] for s in o], w, label="Custo no horizonte", color=BLUE)
    b2 = ax.bar(x + w / 2, [s["evitada"] for s in o], w, label="Perda evitada", color=ORANGE)
    _rotulos(ax, b1, [s["custo_h"] for s in o], lambda v: compacto(v))
    _rotulos(ax, b2, [s["evitada"] for s in o], lambda v: compacto(v))
    ax.set_xticks(x); ax.set_xticklabels([s["curto"] for s in o])
    _estilo(ax, f"Custo × perda evitada em {int(r['v']['horiz'])} meses", "Valor (R\\$)", moeda=True)
    ax.legend(fontsize=8, frameon=False)

def chart_economia(ax, r):
    ax.clear()
    if _sem_dados(ax, r):
        return
    o = r["opts"]; vals = [s["econ"] for s in o]
    bars = ax.bar([s["curto"] for s in o], vals, color=[GREEN if v >= 0 else RED for v in vals], width=.5)
    ax.axhline(0, linewidth=.8, color=INK)
    _rotulos(ax, bars, vals, brl_pdf)
    _estilo(ax, "Economia líquida por solução", "Economia (R\\$)", moeda=True)

def chart_cb(ax, r):
    ax.clear()
    if _sem_dados(ax, r):
        return
    o = r["opts"]; vals = [s["cb"] if math.isfinite(s["cb"]) else 0 for s in o]
    bars = ax.bar([s["curto"] for s in o], vals, color=BLUE, width=.5)
    _rotulos(ax, bars, vals, brl_pdf)
    _estilo(ax, "Custo por 1% de proteção (no horizonte)", "R\\$ por ponto percentual", moeda=True)

def chart_residual(ax, r):
    ax.clear()
    if _sem_dados(ax, r):
        return
    o = r["opts"]; x = np.arange(len(o)); w = .36
    ax.bar(x - w / 2, [r["perda_h"]] * len(o), w, label="Perda sem proteção", color="#98A2B3")
    b = ax.bar(x + w / 2, [s["residual"] for s in o], w, label="Perda residual", color=ORANGE)
    _rotulos(ax, b, [s["residual"] for s in o], lambda v: compacto(v))
    ax.set_xticks(x); ax.set_xticklabels([s["curto"] for s in o])
    _estilo(ax, "Perda sem proteção × perda residual", "Valor no horizonte (R\\$)", moeda=True)
    ax.set_ylim(0, r["perda_h"] * 1.25 or 1)
    ax.legend(fontsize=8, frameon=False, loc="upper center", ncol=2)

def chart_payback(ax, r):
    ax.clear()
    if _sem_dados(ax, r):
        return
    o = r["opts"]; vals = [s["payback"] if math.isfinite(s["payback"]) else 0 for s in o]
    bars = ax.bar([s["curto"] for s in o], vals, color=[BLUE if math.isfinite(s["payback"]) else RED for s in o], width=.5)
    for b, s in zip(bars, o):
        txt = fmt_payback(s["payback"])
        ax.annotate(txt, (b.get_x() + b.get_width() / 2, b.get_height()), xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8, color=RED if not math.isfinite(s["payback"]) else INK)
    hz = r["v"]["horiz"]
    if max(vals + [0]) > 0:
        ax.axhline(hz, color=MUTED, linestyle="--", linewidth=.9)
        ax.text(len(o) - .5, hz, f" horizonte ({int(hz)} meses)", va="bottom", ha="right", fontsize=7.5, color=MUTED)
    ax.set_ylim(0, max(vals + [hz]) * 1.18 if max(vals) > 0 else 1)
    _estilo(ax, "Payback do investimento", "Meses")

def chart_multicriterio(ax, r):
    ax.clear()
    if _sem_dados(ax, r):
        return
    o = r["opts"]
    pb_fin = [s["payback"] for s in o if math.isfinite(s["payback"])]
    pb_cap = (max(pb_fin) * 2 if pb_fin else r["v"]["horiz"] * 2) or 1
    cb_fin = [s["cb"] for s in o if math.isfinite(s["cb"])]
    cb_cap = (max(cb_fin) * 2 if cb_fin else 1) or 1
    crit = {
        "Proteção": ([s["r"] for s in o], True),
        "ROI": ([s["roi"] if s["roi"] is not None else 0 for s in o], True),
        "Economia\nlíquida": ([s["econ"] for s in o], True),
        "Custo por\n1%": ([s["cb"] if math.isfinite(s["cb"]) else cb_cap for s in o], False),
        "Payback": ([s["payback"] if math.isfinite(s["payback"]) else pb_cap for s in o], False),
    }
    def norm(a, beneficio):
        a = np.array(a, dtype=float); lo, hi = a.min(), a.max()
        if hi - lo < EPS:
            return np.full_like(a, 100.0)
        return (a - lo) / (hi - lo) * 100 if beneficio else (hi - a) / (hi - lo) * 100
    dados = np.vstack([norm(vals, ben) for vals, ben in crit.values()]).T
    x = np.arange(len(crit)); w = .8 / len(o)
    cores = [BLUE, ORANGE, GREEN]
    for i, (s, linha) in enumerate(zip(o, dados)):
        ax.bar(x + (i - (len(o) - 1) / 2) * w, linha, w, label=s["nome"], color=cores[i % 3])
    ax.set_xticks(x); ax.set_xticklabels(list(crit.keys()))
    ax.set_ylim(0, 118)
    _estilo(ax, "Análise multicritério (índice 0–100, maior é melhor)", "Índice normalizado")
    ax.legend(fontsize=7.5, loc="upper center", ncol=3, frameon=False)

def fluxo_acumulado(o, r):
    """Resultado acumulado mês a mês: perda evitada acumulada menos as compras feitas até o mês."""
    hz = int(r["v"]["horiz"]); ganho = r["perda_mes"] * o["r"]
    meses = np.arange(0, hz + 1)
    compras = np.array([1 if m == 0 else max(1, math.ceil(m / o["vida"] - EPS)) for m in meses])
    return meses, ganho * meses - o["inv"] * compras

def chart_fluxo(ax, r, apenas=None):
    ax.clear()
    if _sem_dados(ax, r):
        return
    cores = {"cant": BLUE, "est": ORANGE, "div": GREEN}
    for o in r["opts"]:
        if apenas and o["k"] != apenas:
            continue
        m, y = fluxo_acumulado(o, r)
        ax.plot(m, y, marker="o", markersize=2.5, linewidth=1.8, color=cores[o["k"]], label=o["nome"])
        ax.annotate(compacto(y[-1]), (m[-1], y[-1]), xytext=(4, 0), textcoords="offset points", fontsize=7.5, va="center")
    ax.axhline(0, color=INK, linewidth=.8)
    ax.set_xlabel("Mês", fontsize=9)
    _estilo(ax, "Evolução mensal do resultado acumulado", "Resultado acumulado (R\\$)", moeda=True)
    ax.legend(fontsize=7.5, frameon=False)

def sensibilidade(r):
    """Varia cada parâmetro em ±20% e mede a economia líquida da solução recomendada."""
    v, b = r["v"], r["best"]
    if not b:
        return []
    k = b["k"]
    params = [("taxa", "Taxa de avaria"), ("vperd", "Valor por caixa"), ("horiz", "Horizonte"),
              ("ocup", "Fator de ocupação"), ("area", "Área do piso"), ("v_" + k, "Valor unitário"),
              ("r_" + k, "Redução de danos"), ("q_" + k, "Quantidade"), ("l_" + k, "Vida útil")]
    linhas = []
    for key, label in params:
        f = FIELD_BY_KEY[key]

        def em(fator):
            w = dict(v); n = v[key] * fator
            if f[7]:
                n = max(f[4], int(round(n)))
            if f[6] is not None:
                n = min(f[6], n)
            w[key] = n
            m = modelo(w)
            alvo = next(x for x in m["opts"] if x["k"] == k)
            return alvo["econ"], m["best"]["k"] != k

        lo, muda_lo = em(.8); hi, muda_hi = em(1.2)
        if abs(lo - b["econ"]) < .005 and abs(hi - b["econ"]) < .005:
            continue
        linhas.append({"label": label, "lo": lo, "hi": hi, "muda": muda_lo or muda_hi})
    linhas.sort(key=lambda x: max(abs(x["lo"] - b["econ"]), abs(x["hi"] - b["econ"])), reverse=True)
    return linhas

def chart_tornado(ax, r):
    ax.clear()
    linhas = r.get("sens") if r.get("sens") is not None else sensibilidade(r)
    if not r["best"] or not linhas:
        ax.text(.5, .5, "Sem dados de sensibilidade", ha="center", va="center", transform=ax.transAxes, color=MUTED)
        ax.set_xticks([]); ax.set_yticks([])
        return
    base = r["best"]["econ"]; y = np.arange(len(linhas))[::-1]; h = .38
    for yi, l in zip(y, linhas):
        ax.barh(yi + h / 2, l["lo"] - base, h, left=base, color=ORANGE, label="Parâmetro −20%" if yi == y[0] else None)
        ax.barh(yi - h / 2, l["hi"] - base, h, left=base, color=BLUE, label="Parâmetro +20%" if yi == y[0] else None)
    ax.axvline(base, color=INK, linewidth=1)
    ax.set_yticks(y); ax.set_yticklabels([("★ " if l["muda"] else "") + l["label"] for l in linhas], fontsize=8)
    ax.xaxis.set_major_formatter(FuncFormatter(eixo_brl))
    ax.set_title(f"Sensibilidade (±20%): economia de {r['best']['nome']}", fontsize=12, fontweight="bold", color=NAVY, pad=10)
    ax.grid(axis="x", alpha=.2); ax.spines[["top", "right"]].set_visible(False); ax.tick_params(labelsize=8)
    ax.legend(fontsize=7.5, frameon=False, loc="lower right")
    ax.text(0, -.16, "★ = uma variação de 20% nesse parâmetro muda a solução recomendada. Linha preta = economia atual.",
            transform=ax.transAxes, fontsize=7.5, color=MUTED)

# Todos os gráficos do programa: (função, título curto, arquivo PNG)
GRAFICOS = [
    (chart_custo_evitada, "Custo × perda evitada", "01_custo_perda_evitada.png"),
    (chart_economia, "Economia líquida", "02_economia_liquida.png"),
    (chart_cb, "Custo por 1% de proteção", "03_custo_por_1pct.png"),
    (chart_residual, "Perda residual", "04_perda_residual.png"),
    (chart_payback, "Payback", "05_payback.png"),
    (chart_multicriterio, "Multicritério", "06_multicriterio.png"),
    (chart_fluxo, "Evolução mensal", "07_evolucao_mensal.png"),
    (chart_tornado, "Sensibilidade", "08_sensibilidade.png"),
]

# Relatórios disponíveis no PDF (podem ser escolhidos, gerados juntos ou um arquivo por relatório)
SECOES = [
    ("resumo", "Resumo do cenário e parâmetros"),
    ("comparativo", "Comparativo das soluções e leitura do resultado"),
    ("financeiro", "Gráficos: custo × perda evitada e economia líquida"),
    ("eficiencia", "Gráficos: custo por 1% de proteção e perda residual"),
    ("retorno", "Gráficos: payback e análise multicritério"),
    ("evolucao", "Evolução mensal acumulada e sensibilidade (±20%)"),
    ("solucoes", "Ficha detalhada de cada solução"),
    ("documentos", "Lista de documentos do projeto"),
]


# ===== Interface =====
class Scrollable(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, padding=(6, 0, 10, 10))
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.win, width=e.width))
        # A roda do mouse rola só a aba sob o cursor (antes, a última aba criada capturava tudo).
        self.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, e):
        if self.canvas.yview() != (0.0, 1.0):
            self.canvas.yview_scroll(int(-e.delta / 120), "units")


class Simulator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1320, sw - 60), min(880, sh - 100)
        self.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 3)}")
        self.minsize(min(980, sw - 40), min(640, sh - 80))
        if sw <= 1400:
            try:
                self.state("zoomed")
            except tk.TclError:
                pass
        self.configure(bg=BG)
        try:
            self.iconbitmap(default=str(resource_path("simulador.ico")))
        except tk.TclError:
            pass
        self.vars, self.entries, self.result, self.cenario_nome = {}, {}, None, ""
        self._after = None
        self._style()
        self._header()
        self._tabs()
        self._statusbar()
        self._load_last()
        for var in self.vars.values():
            var.trace_add("write", lambda *a: self._schedule())
        self.calculate(show_errors=False)

    # ----- estrutura -----
    def report_callback_exception(self, exc, val, tb):
        logging.error("Erro não tratado:\n%s", "".join(traceback.format_exception(exc, val, tb)))
        messagebox.showerror("Erro inesperado", f"{val}\n\nOs detalhes foram salvos em:\n{data_dir() / 'simulador.log'}")

    def _style(self):
        s = ttk.Style(self); s.theme_use("clam")
        s.configure(".", font=("Segoe UI", 10))
        s.configure("TFrame", background=BG)
        s.configure("Card.TFrame", background=WHITE)
        s.configure("TLabel", background=BG, foreground=INK)
        s.configure("Card.TLabel", background=WHITE, foreground=INK)
        s.configure("Muted.TLabel", background=WHITE, foreground=MUTED, font=("Segoe UI", 9))
        s.configure("H2.TLabel", background=BG, foreground=NAVY, font=("Segoe UI", 15, "bold"))
        s.configure("H3.TLabel", background=WHITE, foreground=NAVY, font=("Segoe UI", 11, "bold"))
        s.configure("Metric.TLabel", background=WHITE, foreground=NAVY, font=("Segoe UI", 19, "bold"))
        s.configure("Card.TCheckbutton", background=WHITE)
        s.configure("Invalid.TEntry", fieldbackground=PALE_RED, foreground=RED)
        s.configure("Primary.TButton", background=BLUE, foreground="white", padding=8)
        s.map("Primary.TButton", background=[("active", "#0C447C")])
        s.configure("Orange.TButton", background=ORANGE, foreground="white", padding=8)
        s.map("Orange.TButton", background=[("active", "#B84000")])
        s.configure("TButton", padding=7)
        s.configure("Treeview", rowheight=28, background="white", fieldbackground="white")
        s.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        s.configure("Status.TLabel", background=WHITE, foreground=MUTED, padding=(12, 4))

    def _header(self):
        h = tk.Frame(self, bg=NAVY); h.pack(fill="x")
        tk.Frame(self, bg=ORANGE, height=4).pack(fill="x")
        try:
            self._logo = tk.PhotoImage(file=str(resource_path("logo_72.png")))
            tk.Label(h, image=self._logo, bg=WHITE, bd=0).pack(side="left", padx=(22, 16), pady=14)
        except tk.TclError:
            tk.Label(h, text="UCE", bg=NAVY, fg="#FF9D52", font=("Segoe UI", 19, "bold"),
                     bd=2, relief="solid", padx=10, pady=8).pack(side="left", padx=(22, 16), pady=14)
        box = tk.Frame(h, bg=NAVY); box.pack(side="left", pady=12, fill="x", expand=True)
        tk.Label(box, text="Simulador Inteligente de Armazenagem", bg=NAVY, fg="white",
                 font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(box, text="Ciência de Dados aplicada à proteção de embalagens e tomada de decisão • UCE II",
                 bg=NAVY, fg="#E5EDF7", font=("Segoe UI", 10)).pack(anchor="w")
        tk.Label(box, text=f"Faculdade SENAI • Contagem (MG) · Tecnólogo em Ciência de Dados\n"
                           f"Equipe: {EQUIPE}  |  Orientadora: {ORIENTADORA}",
                 bg=NAVY, fg="#D1DBEA", font=("Segoe UI", 9), justify="left").pack(anchor="w", pady=(4, 0))
        tk.Label(h, text=f"v{VERSION}", bg=NAVY, fg="#D1DBEA", font=("Segoe UI", 9)).pack(side="right", anchor="n", padx=16, pady=12)

    def _statusbar(self):
        self.status = ttk.Label(self, text="", style="Status.TLabel", anchor="w")
        self.status.pack(fill="x", side="bottom")

    def set_status(self, txt, bad=False):
        self.status.configure(text=txt, foreground=RED if bad else MUTED)

    def _tabs(self):
        self.nb = ttk.Notebook(self); self.nb.pack(fill="both", expand=True, padx=14, pady=(10, 6))
        self.pages = {}
        for key, title in [("data", "01 · Dados"), ("dash", "02 · Dashboard"), ("compare", "03 · Comparativo"),
                           ("charts", "04 · Análise"), ("report", "05 · Relatório"), ("docs", "06 · Documentos")]:
            sf = Scrollable(self.nb); self.nb.add(sf, text=title); self.pages[key] = sf.inner
        self._data_page(); self._dash_page(); self._compare_page(); self._charts_page(); self._report_page(); self._documents_page()

    def card(self, parent, pad=14):
        return ttk.Frame(parent, style="Card.TFrame", padding=pad)

    def field(self, parent, key):
        f = FIELD_BY_KEY[key]
        ttk.Label(parent, text=f"{f[1]} ({f[2]})", style="Card.TLabel").pack(anchor="w", pady=(6, 2))
        var = tk.StringVar(value=nfmt(f[3], 4).rstrip("0").rstrip(",") if not f[7] else str(f[3]))
        self.vars[key] = var
        e = ttk.Entry(parent, textvariable=var); e.pack(fill="x")
        self.entries[key] = e

    def _data_page(self):
        p = self.pages["data"]
        ttk.Label(p, text="Dados do armazém", style="H2.TLabel").pack(anchor="w", pady=(12, 8))
        row = ttk.Frame(p); row.pack(fill="x")
        for i, (titulo, grupo, dica) in enumerate([
                ("Armazém", "armazem", "Caixas por camada = piso(área × ocupação ÷ base da caixa)."),
                ("Caixa", "caixa", "A altura limita as camadas que cabem no pé-direito."),
                ("Avarias e horizonte", "avaria", "Perda mensal = caixas × taxa de avaria × valor.")]):
            c = self.card(row); c.grid(row=0, column=i, sticky="nsew", padx=5); row.columnconfigure(i, weight=1, uniform="a")
            ttk.Label(c, text=titulo, style="H3.TLabel").pack(anchor="w")
            for f in FIELDS:
                if f[8] == grupo:
                    self.field(c, f[0])
            ttk.Label(c, text=dica, style="Muted.TLabel", wraplength=330).pack(anchor="w", pady=(10, 0))

        ttk.Label(p, text="Soluções de proteção", style="H2.TLabel").pack(anchor="w", pady=(18, 8))
        row = ttk.Frame(p); row.pack(fill="x")
        for i, s in enumerate(SOLS):
            c = self.card(row); c.grid(row=0, column=i, sticky="nsew", padx=5); row.columnconfigure(i, weight=1, uniform="b")
            top = ttk.Frame(c, style="Card.TFrame"); top.pack(fill="x")
            ttk.Label(top, text=s["nome"], style="H3.TLabel").pack(side="left")
            var = tk.BooleanVar(value=True); self.vars["on_" + s["k"]] = var
            ttk.Checkbutton(top, text="Incluir", variable=var, style="Card.TCheckbutton").pack(side="right")
            for f in FIELDS:
                if f[8] == s["k"]:
                    self.field(c, f[0])
            dica = ("Investimento = caixas × qtd. por caixa × valor. Recompra a cada vida útil."
                    if s["por_caixa"] else "Investimento = quantidade × valor. Recompra ao fim da vida útil.")
            ttk.Label(c, text=dica, style="Muted.TLabel", wraplength=330).pack(anchor="w", pady=(10, 0))

        ttk.Label(p, text="Critério de decisão", style="H2.TLabel").pack(anchor="w", pady=(18, 8))
        c = self.card(p); c.pack(fill="x", padx=5)
        self.crit_names = {v[0]: k for k, v in CRITERIOS.items()}
        self.vars["criterio"] = tk.StringVar(value=CRITERIOS["econ"][0])
        ttk.Label(c, text="Recomendar a solução com:", style="Card.TLabel").pack(side="left")
        ttk.Combobox(c, textvariable=self.vars["criterio"], values=list(self.crit_names), state="readonly",
                     width=38).pack(side="left", padx=10)

        a = ttk.Frame(p); a.pack(fill="x", pady=14)
        for txt, cmd, sty in [("Calcular cenário", lambda: self.calculate(True), "Primary.TButton"),
                              ("Restaurar padrões", self.reset, "TButton"),
                              ("Salvar cenário (JSON)", self.save_scenario, "TButton"),
                              ("Abrir cenário (JSON)", self.open_scenario, "TButton")]:
            ttk.Button(a, text=txt, command=cmd, style=sty).pack(side="left", padx=4)
        ttk.Label(a, text="O cálculo é refeito automaticamente ao digitar.", foreground=MUTED).pack(side="left", padx=12)

    def _dash_page(self):
        p = self.pages["dash"]
        ttk.Label(p, text="Dashboard do cenário", style="H2.TLabel").pack(anchor="w", pady=(12, 8))
        grid = ttk.Frame(p); grid.pack(fill="x"); self.metrics = {}
        specs = [("m1", "Caixas por camada"), ("m2", "Camadas efetivas"), ("m3", "Total de caixas"),
                 ("m4", "Avarias sem proteção"), ("m5", "Perda sem proteção"), ("m6", "Perda no horizonte")]
        for i, (k, title) in enumerate(specs):
            c = self.card(grid); c.grid(row=i // 3, column=i % 3, sticky="nsew", padx=5, pady=5)
            grid.columnconfigure(i % 3, weight=1, uniform="m")
            ttk.Label(c, text=title, style="Card.TLabel").pack(anchor="w")
            val = ttk.Label(c, text="—", style="Metric.TLabel"); val.pack(anchor="w", pady=4)
            sub = ttk.Label(c, text="", style="Muted.TLabel"); sub.pack(anchor="w")
            self.metrics[k] = (val, sub)
        c = self.card(p); c.pack(fill="both", expand=True, pady=12, padx=5)
        ttk.Label(c, text="Avisos e síntese", style="H3.TLabel").pack(anchor="w")
        self.summary = tk.Text(c, height=12, bg=WHITE, fg=INK, font=("Segoe UI", 10), bd=0, wrap="word")
        self.summary.pack(fill="both", expand=True, pady=(8, 0))
        for tag, cor in (("bad", RED), ("warn", AMBER), ("info", BLUE)):
            self.summary.tag_configure(tag, foreground=cor, font=("Segoe UI", 10, "bold"))

    def _compare_page(self):
        p = self.pages["compare"]
        ttk.Label(p, text="Comparativo das soluções", style="H2.TLabel").pack(anchor="w", pady=(12, 8))
        row = ttk.Frame(p); row.pack(fill="x"); self.solcards = []
        for i in range(3):
            c = self.card(row); c.grid(row=0, column=i, sticky="nsew", padx=5); row.columnconfigure(i, weight=1, uniform="c")
            title = ttk.Label(c, text="—", style="H3.TLabel"); title.pack(anchor="w")
            txt = tk.Label(c, bg=WHITE, fg=INK, justify="left", anchor="nw", font=("Segoe UI", 10), pady=8)
            txt.pack(fill="x"); self.solcards.append((title, txt))
        c = self.card(p); c.pack(fill="x", pady=14, padx=5)
        self.tree_title = ttk.Label(c, text="Tabela analítica", style="H3.TLabel"); self.tree_title.pack(anchor="w", pady=(0, 8))
        cols = ("rank", "sol", "q", "inv", "custo", "prot", "avoid", "net", "roi", "pb", "cb")
        heads = ("#", "Solução", "Qtd.", "Investimento", "Custo no horizonte", "Proteção", "Perda evitada",
                 "Economia líquida", "ROI", "Payback", "Custo/1%")
        self.tree = ttk.Treeview(c, columns=cols, show="headings", height=4)
        for col, hd in zip(cols, heads):
            self.tree.heading(col, text=hd); self.tree.column(col, width=110, anchor="center")
        self.tree.column("rank", width=34); self.tree.column("sol", width=170, anchor="w")
        self.tree.pack(fill="x")
        self.tree.tag_configure("best", background="#EDF6FF")
        self.tree.tag_configure("neg", foreground=RED)
        ttk.Button(p, text="Exportar resultados CSV", command=self.export_csv).pack(anchor="e", padx=5)

    def _charts_page(self):
        p = self.pages["charts"]
        ttk.Label(p, text="Análise gráfica", style="H2.TLabel").pack(anchor="w", pady=(12, 2))
        ttk.Label(p, text=f"{len(GRAFICOS)} gráficos, os mesmos do relatório PDF.", foreground=MUTED).pack(anchor="w", pady=(0, 8))
        self.figs, self.canvases = [], []
        for _ in GRAFICOS:
            fig = Figure(figsize=(8, 3.4), dpi=100)
            fig.add_subplot(111)
            cv = FigureCanvasTkAgg(fig, p); cv.get_tk_widget().pack(fill="both", expand=True, pady=6)
            self.figs.append(fig); self.canvases.append(cv)

    def _report_page(self):
        p = self.pages["report"]
        ttk.Label(p, text="Central de relatórios", style="H2.TLabel").pack(anchor="w", pady=(12, 8))
        c = self.card(p); c.pack(fill="x", padx=5)
        ttk.Label(c, text="Escolha os relatórios", style="H3.TLabel").pack(anchor="w")
        ttk.Label(c, text="Gere tudo num único PDF, um PDF para cada relatório, ou envie direto para a impressora padrão do Windows.",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 8))
        grade = ttk.Frame(c, style="Card.TFrame"); grade.pack(fill="x")
        self.secoes_vars = {}
        for i, (sid, titulo) in enumerate(SECOES):
            var = tk.BooleanVar(value=True); self.secoes_vars[sid] = var
            ttk.Checkbutton(grade, text=f"{i + 1}. {titulo}", variable=var, style="Card.TCheckbutton").grid(
                row=i // 2, column=i % 2, sticky="w", padx=(0, 30), pady=2)
        sel = ttk.Frame(c, style="Card.TFrame"); sel.pack(fill="x", pady=(8, 0))
        ttk.Button(sel, text="Marcar todos", command=lambda: [x.set(True) for x in self.secoes_vars.values()]).pack(side="left")
        ttk.Button(sel, text="Desmarcar todos", command=lambda: [x.set(False) for x in self.secoes_vars.values()]).pack(side="left", padx=6)
        a = ttk.Frame(c, style="Card.TFrame"); a.pack(fill="x", pady=(12, 0))
        for txt, cmd, sty in [("Gerar PDF dos selecionados", self.export_pdf, "Orange.TButton"),
                              ("Imprimir selecionados", self.print_reports, "Primary.TButton"),
                              ("Gerar um PDF por relatório", self.export_pdfs_separados, "TButton")]:
            ttk.Button(a, text=txt, command=cmd, style=sty).pack(side="left", padx=(0, 8))
        a2 = ttk.Frame(c, style="Card.TFrame"); a2.pack(fill="x", pady=(8, 0))
        for txt, cmd in [("Exportar CSV", self.export_csv), ("Backup JSON", self.export_json),
                         ("Salvar os 8 gráficos PNG", self.export_pngs), ("Exportar pacote completo", self.export_package)]:
            ttk.Button(a2, text=txt, command=cmd).pack(side="left", padx=(0, 8))

        ttk.Label(p, text="Resultado técnico", style="H2.TLabel").pack(anchor="w", pady=(18, 8))
        c = self.card(p); c.pack(fill="both", expand=True, padx=5)
        self.report = tk.Text(c, height=24, bg=WHITE, fg=INK, font=("Segoe UI", 11), bd=0, wrap="word")
        self.report.pack(fill="both", expand=True)
        self.report.tag_configure("h", font=("Segoe UI", 13, "bold"), foreground=NAVY, spacing3=6)
        self.report.tag_configure("h2", font=("Segoe UI", 12, "bold"), foreground=NAVY, spacing1=6, spacing3=4)
        self.report.tag_configure("b", font=("Segoe UI", 11, "bold"))

    def _documents_page(self):
        migrate_legacy_reports()
        init_document_database()
        p = self.pages["docs"]
        ttk.Label(p, text="Documentos do projeto", style="H2.TLabel").pack(anchor="w", pady=(12, 8))

        c = self.card(p); c.pack(fill="x", padx=5, pady=(0, 12))
        ttk.Label(c, text="Acesso rápido", style="H3.TLabel").pack(anchor="w")
        ttk.Label(c, text="Os três relatórios principais do trabalho. Se ainda não houver arquivo, o programa pede para escolher um.",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 10))
        botoes = ttk.Frame(c, style="Card.TFrame"); botoes.pack(fill="x")
        for tipo, (titulo, _arq) in DOCUMENTOS_FIXOS.items():
            ttk.Button(botoes, text=titulo, command=lambda t=tipo: self.abrir_documento_fixo(t),
                       style="Primary.TButton").pack(side="left", padx=(0, 10), pady=4)
        self.docs_status = ttk.Label(c, text="", style="Card.TLabel"); self.docs_status.pack(anchor="w", pady=(10, 0))

        c = self.card(p); c.pack(fill="both", expand=True, padx=5)
        topo = ttk.Frame(c, style="Card.TFrame"); topo.pack(fill="x")
        ttk.Label(topo, text="Biblioteca de documentos do trabalho", style="H3.TLabel").pack(side="left")
        self.docs_count = ttk.Label(topo, text="", style="Muted.TLabel"); self.docs_count.pack(side="left", padx=12)
        ttk.Label(c, text="Adicione quantos documentos quiser: PDF, Word, Excel, PowerPoint, imagens e outros. "
                          "O programa guarda uma cópia de cada arquivo e registra no banco de dados.",
                  style="Muted.TLabel", wraplength=1000).pack(anchor="w", pady=(2, 10))

        barra = ttk.Frame(c, style="Card.TFrame"); barra.pack(fill="x", pady=(0, 8))
        ttk.Button(barra, text="Adicionar documentos…", command=self.doc_adicionar, style="Orange.TButton").pack(side="left")
        for txt, cmd in [("Abrir", self.doc_abrir), ("Imprimir", self.doc_imprimir), ("Editar dados", self.doc_editar),
                         ("Substituir arquivo", self.doc_substituir), ("Remover", self.doc_remover),
                         ("Abrir pasta", lambda: open_path(reports_dir()))]:
            ttk.Button(barra, text=txt, command=cmd).pack(side="left", padx=(8, 0))
        busca = ttk.Frame(c, style="Card.TFrame"); busca.pack(fill="x", pady=(0, 8))
        ttk.Label(busca, text="Buscar:", style="Card.TLabel").pack(side="left")
        self.doc_filtro = tk.StringVar()
        self.doc_filtro.trace_add("write", lambda *a: self.atualizar_documentos())
        ttk.Entry(busca, textvariable=self.doc_filtro, width=40).pack(side="left", padx=8)

        cols = ("n", "titulo", "categoria", "arquivo", "tamanho", "data")
        heads = ("#", "Título", "Categoria", "Arquivo original", "Tamanho", "Atualizado em")
        frame_tv = ttk.Frame(c, style="Card.TFrame"); frame_tv.pack(fill="both", expand=True)
        self.doc_tree = ttk.Treeview(frame_tv, columns=cols, show="headings", height=14, selectmode="extended")
        for col, hd in zip(cols, heads):
            self.doc_tree.heading(col, text=hd)
        for col, w, anc in [("n", 40, "center"), ("titulo", 260, "w"), ("categoria", 170, "w"), ("arquivo", 260, "w"),
                            ("tamanho", 80, "e"), ("data", 130, "center")]:
            self.doc_tree.column(col, width=w, anchor=anc)
        sb = ttk.Scrollbar(frame_tv, orient="vertical", command=self.doc_tree.yview)
        self.doc_tree.configure(yscrollcommand=sb.set)
        self.doc_tree.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        self.doc_tree.tag_configure("vazio", foreground=MUTED)
        self.doc_tree.tag_configure("fixo", font=("Segoe UI", 10, "bold"))
        self.doc_tree.bind("<Double-1>", lambda e: self.doc_abrir())
        self.doc_tree.bind("<Return>", lambda e: self.doc_abrir())
        self.doc_tree.bind("<Delete>", lambda e: self.doc_remover())
        ttk.Label(c, text=f"Pasta dos arquivos: {reports_dir()}", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
        self.atualizar_documentos()

    # ----- documentos -----
    def atualizar_documentos(self):
        if not hasattr(self, "doc_tree"):
            return
        todos = listar_documentos()
        docs = listar_documentos(self.doc_filtro.get()) if self.doc_filtro.get().strip() else todos
        self.doc_tree.delete(*self.doc_tree.get_children())
        for i, d in enumerate(docs, 1):
            vazio = not d["arquivo"] or not caminho_documento(d).exists()
            tags = (("vazio",) if vazio else ()) + (("fixo",) if d["tipo"] else ())
            self.doc_tree.insert("", "end", iid=str(d["id"]), tags=tags, values=(
                i, d["titulo"], d["categoria"], "aguardando arquivo" if vazio else (d["nome_original"] or d["arquivo"]),
                "—" if vazio else tamanho_legivel(d["tamanho"]), (d["atualizado_em"] or "")[:16]))
        n_ok = sum(1 for d in todos if d["arquivo"] and caminho_documento(d).exists())
        self.docs_count.config(text=f"{n_ok} arquivo(s) armazenado(s)")
        linhas = []
        for tipo, (titulo, _a) in DOCUMENTOS_FIXOS.items():
            d = obter_documento(tipo=tipo)
            ok = d and d["arquivo"] and caminho_documento(d).exists()
            linhas.append(("✓ " if ok else "○ ") + titulo + ": " + ("disponível" if ok else "aguardando arquivo"))
        self.docs_status.config(text="\n".join(linhas))

    def _doc_selecionados(self, um=False):
        ids = [int(i) for i in self.doc_tree.selection()]
        if not ids:
            messagebox.showinfo("Documentos", "Selecione um documento na lista.")
            return []
        if um and len(ids) > 1:
            messagebox.showinfo("Documentos", "Selecione apenas um documento para esta ação.")
            return []
        return ids

    def _abrir_doc(self, doc, imprimir=False):
        p = caminho_documento(doc)
        if not p or not p.exists():
            if messagebox.askyesno("Documento sem arquivo", f"“{doc['titulo']}” ainda não tem arquivo.\n\nEscolher o arquivo agora?"):
                self._doc_escolher_arquivo(doc["id"])
            return
        try:
            imprimir_arquivo(p) if imprimir else open_path(p)
        except OSError as e:
            if imprimir:
                messagebox.showwarning("Impressão", f"O Windows não tem um programa associado para imprimir este tipo de arquivo "
                                                    f"({p.suffix}). O arquivo será aberto para você imprimir por ele.\n\n{e}")
                try:
                    open_path(p)
                except OSError:
                    pass
            else:
                messagebox.showerror("Erro", f"Não foi possível abrir o documento.\n\n{e}")

    def abrir_documento_fixo(self, tipo):
        init_document_database()
        self._abrir_doc(obter_documento(tipo=tipo))

    def doc_abrir(self):
        for i in self._doc_selecionados():
            self._abrir_doc(obter_documento(i))

    def doc_imprimir(self):
        ids = self._doc_selecionados()
        if ids and messagebox.askyesno("Imprimir", f"Enviar {len(ids)} documento(s) para a impressora padrão?"):
            for i in ids:
                self._abrir_doc(obter_documento(i), imprimir=True)

    def doc_adicionar(self):
        arquivos = filedialog.askopenfilenames(title="Adicionar documentos do trabalho", filetypes=TIPOS_ARQUIVO)
        if not arquivos:
            return
        ok, falhas, ultimo = 0, [], None
        self.config(cursor="watch"); self.update_idletasks()
        try:
            for a in arquivos:
                try:
                    ultimo = adicionar_documento(a); ok += 1
                except OSError as e:
                    falhas.append(f"{Path(a).name}: {e}")
        finally:
            self.config(cursor="")
        self.atualizar_documentos()
        if ok == 1 and not falhas:
            self.doc_tree.selection_set(str(ultimo)); self.doc_tree.see(str(ultimo))
            self.doc_editar()
        else:
            msg = f"{ok} documento(s) adicionado(s)."
            if falhas:
                msg += "\n\nNão foi possível copiar:\n" + "\n".join(falhas)
            msg += "\n\nUse “Editar dados” para ajustar título e categoria."
            messagebox.showinfo("Documentos", msg)
        self.set_status(f"{ok} documento(s) adicionado(s) à biblioteca.")

    def _doc_escolher_arquivo(self, doc_id):
        doc = obter_documento(doc_id)
        origem = filedialog.askopenfilename(title=f"Arquivo para “{doc['titulo']}”", filetypes=TIPOS_ARQUIVO)
        if not origem:
            return
        try:
            substituir_arquivo(doc_id, origem)
        except PermissionError:
            messagebox.showerror("Arquivo em uso", "Feche o arquivo no outro programa e tente de novo.")
            return
        except OSError as e:
            messagebox.showerror("Erro", str(e)); return
        self.atualizar_documentos()
        self.set_status(f"Arquivo de “{doc['titulo']}” atualizado.")

    def doc_substituir(self):
        ids = self._doc_selecionados(um=True)
        if ids:
            self._doc_escolher_arquivo(ids[0])

    def doc_remover(self):
        ids = self._doc_selecionados()
        if not ids:
            return
        docs = [obter_documento(i) for i in ids]
        nomes = "\n".join("• " + d["titulo"] for d in docs[:12]) + ("\n…" if len(docs) > 12 else "")
        if not messagebox.askyesno("Remover documentos", f"Remover {len(docs)} documento(s) da biblioteca?\n\n{nomes}\n\n"
                                   "A cópia guardada pelo programa será apagada. O arquivo original não é afetado.\n"
                                   "Nos três documentos de acesso rápido, só o arquivo é retirado; o atalho continua."):
            return
        for d in docs:
            try:
                remover_documento(d["id"])
            except PermissionError:
                messagebox.showerror("Arquivo em uso", f"Feche “{d['titulo']}” no outro programa e tente de novo.")
        self.atualizar_documentos()

    def doc_editar(self):
        ids = self._doc_selecionados(um=True)
        if not ids:
            return
        d = obter_documento(ids[0])
        win = tk.Toplevel(self); win.title("Dados do documento"); win.configure(bg=BG)
        win.transient(self); win.grab_set(); win.resizable(False, False)
        frm = ttk.Frame(win, padding=20); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Título").grid(row=0, column=0, sticky="w")
        titulo = tk.StringVar(value=d["titulo"])
        ent = ttk.Entry(frm, textvariable=titulo, width=60); ent.grid(row=1, column=0, sticky="ew", pady=(2, 10))
        ttk.Label(frm, text="Categoria").grid(row=2, column=0, sticky="w")
        cat = tk.StringVar(value=d["categoria"])
        ttk.Combobox(frm, textvariable=cat, values=CATEGORIAS, width=58).grid(row=3, column=0, sticky="ew", pady=(2, 10))
        ttk.Label(frm, text="Observações").grid(row=4, column=0, sticky="w")
        obs = tk.Text(frm, height=5, width=60, font=("Segoe UI", 10)); obs.grid(row=5, column=0, sticky="ew", pady=(2, 10))
        obs.insert("1.0", d["observacoes"] or "")
        ttk.Label(frm, text=f"Arquivo: {d['nome_original'] or 'nenhum'}", foreground=MUTED).grid(row=6, column=0, sticky="w")
        if d["tipo"]:
            ttk.Label(frm, text="Documento de acesso rápido: o título pode mudar, o atalho continua.", foreground=MUTED).grid(row=7, column=0, sticky="w")

        def salvar():
            t = titulo.get().strip()
            if not t:
                messagebox.showerror("Título obrigatório", "Informe um título para o documento.", parent=win); return
            atualizar_documento(d["id"], t, cat.get().strip() or "Documento do trabalho", obs.get("1.0", "end").strip())
            win.destroy(); self.atualizar_documentos()

        bts = ttk.Frame(frm); bts.grid(row=8, column=0, sticky="e", pady=(14, 0))
        ttk.Button(bts, text="Cancelar", command=win.destroy).pack(side="right")
        ttk.Button(bts, text="Salvar", command=salvar, style="Primary.TButton").pack(side="right", padx=8)
        win.bind("<Return>", lambda e: salvar() if e.widget is not obs else None)
        ent.focus_set(); ent.select_range(0, "end")

    # ----- leitura e cálculo -----
    def read_values(self):
        v, erros = {}, []
        for s in SOLS:
            v["on_" + s["k"]] = bool(self.vars["on_" + s["k"]].get())
        for key, label, unit, default, vmin, min_ex, vmax, inteiro, grupo in FIELDS:
            raw = self.vars[key].get().strip().replace(" ", "")
            if raw.count(",") == 1 and "." in raw:
                raw = raw.replace(".", "")
            raw = raw.replace(",", ".")
            desligada = grupo in v.get("_sols", [s["k"] for s in SOLS]) and not v.get("on_" + grupo, True)
            msg = ""
            try:
                n = float(raw)
                if not math.isfinite(n):
                    raise ValueError
            except ValueError:
                n, msg = default, "informe um número"
            if not msg:
                if (n <= vmin) if min_ex else (n < vmin):
                    msg = f"deve ser maior que {nfmt(vmin, 0)}" if min_ex else f"mínimo {nfmt(vmin, 0)}"
                elif vmax is not None and n > vmax:
                    msg = f"máximo {nfmt(vmax, 0)}"
                elif inteiro and abs(n - round(n)) > EPS:
                    msg = "use um número inteiro"
            if desligada:
                msg = ""
            self.entries[key].configure(style="Invalid.TEntry" if msg else "TEntry")
            if msg:
                nome = label if grupo not in [s["k"] for s in SOLS] else f"{next(s['nome'] for s in SOLS if s['k'] == grupo)}: {label}"
                erros.append(f"{nome} – {msg}")
            v[key] = int(round(n)) if inteiro and not msg else n
        v["criterio"] = self.crit_names.get(self.vars["criterio"].get(), "econ")
        return v, erros

    def _schedule(self):
        if self._after:
            self.after_cancel(self._after)
        self._after = self.after(450, lambda: self.calculate(show_errors=False))

    def calculate(self, show_errors=True):
        self._after = None
        v, erros = self.read_values()
        if erros:
            self.set_status(f"Corrija {len(erros)} campo(s) destacado(s). Os resultados mostrados são do último cálculo válido.", bad=True)
            if show_errors:
                messagebox.showerror("Dados inválidos", "Corrija os campos destacados em vermelho:\n\n• " + "\n• ".join(erros))
            return False
        self.result = modelo(v)
        self.result["sens"] = sensibilidade(self.result)
        self.render()
        self._save_last()
        self.set_status(f"Cálculo atualizado às {datetime.now():%H:%M:%S}.  Dados do programa: {data_dir()}")
        return True

    def ensure_result(self):
        if not self.calculate(show_errors=True):
            return False
        if not self.result["opts"]:
            messagebox.showwarning("Sem soluções", "Inclua pelo menos uma solução antes de exportar.")
            return False
        return True

    # ----- renderização -----
    def render(self):
        r = self.result; v = r["v"]; b = r["best"]
        vals = [
            (nfmt(r["por_camada"], 0), f"área útil {nfmt(r['area_util'])} m² de {nfmt(v['area'])} m²"),
            (nfmt(r["camadas"], 0), "limitado pelo pé-direito" if r["lim_pe"] else "limitado pelo empilhamento"),
            (nfmt(r["total"], 0), f"volume por caixa {nfmt(r['volume'], 4)} m³"),
            (nfmt(r["avarias_mes"], 1) + " /mês", f"{nfmt(v['taxa'], 1)}% das caixas por mês"),
            (brl(r["perda_mes"]) + " /mês", f"{brl(v['vperd'])} por caixa danificada"),
            (brl(r["perda_h"]), f"{v['horiz']} meses sem proteção"),
        ]
        for k, (val, sub) in zip(["m1", "m2", "m3", "m4", "m5", "m6"], vals):
            self.metrics[k][0].config(text=val); self.metrics[k][1].config(text=sub)

        self.summary.delete("1.0", "end")
        for tipo, txt in alertas(r):
            self.summary.insert("end", {"bad": "ATENÇÃO: ", "warn": "AVISO: ", "info": "NOTA: "}[tipo], tipo)
            self.summary.insert("end", txt + "\n\n")
        self.summary.insert("end",
            f"Área útil: {nfmt(r['area_util'])} m² ({nfmt(v['ocup'], 0)}% de {nfmt(v['area'])} m²) · base da caixa {nfmt(r['area_cx'], 4)} m²\n"
            f"Caixas por camada: {r['por_camada']} · camadas: {r['camadas']} · total: {r['total']} caixas\n"
            f"Avarias sem proteção: {nfmt(r['avarias_mes'], 1)} caixas/mês · perda mensal {brl(r['perda_mes'])}\n"
            f"Perda em {v['horiz']} meses sem proteção: {brl(r['perda_h'])}\n"
            f"Critério de recomendação: {CRITERIOS[v['criterio']][0].lower()}")

        por_k = {o["k"]: o for o in r["opts"]}
        for (title, txt), s in zip(self.solcards, SOLS):
            o = por_k.get(s["k"])
            if not o:
                title.config(text=s["nome"]); txt.config(fg=MUTED, text="Não incluída na análise.")
                continue
            title.config(text=f"#{o['rank']}  {o['nome']}" + ("   ★ RECOMENDADA" if o is b else ""))
            txt.config(fg=GREEN if o["econ"] > 0 else RED,
                       text=f"Proteção: {pct(o['r'] * 100)}\nInvestimento inicial: {brl(o['inv'])}\n"
                            f"Custo no horizonte: {brl(o['custo_h'])}" + (f" ({o['ciclos']} compras)" if o["ciclos"] > 1 else "") +
                            f"\nPerda evitada: {brl(o['evitada'])}\nEconomia líquida: {brl(o['econ'])}\n"
                            f"ROI: {pct(o['roi'])}\nPayback: {fmt_payback(o['payback'])}\nCusto / 1% proteção: {fmt_cb(o['cb'])}")
        self.tree_title.config(text=f"Tabela analítica · ordenada por: {CRITERIOS[v['criterio']][0].lower()}")
        self.tree.delete(*self.tree.get_children())
        for o in r["ranked"]:
            tags = (("best",) if o is b else ()) + (("neg",) if o["econ"] < 0 else ())
            self.tree.insert("", "end", values=(o["rank"], o["nome"], nfmt(o["qtd"], 0), brl(o["inv"]), brl(o["custo_h"]),
                                                pct(o["r"] * 100), brl(o["evitada"]), brl(o["econ"]), pct(o["roi"]),
                                                fmt_payback(o["payback"]), fmt_cb(o["cb"])), tags=tags)

        for fig, (fn, _t, _arq) in zip(self.figs, GRAFICOS):
            fn(fig.axes[0], r); fig.tight_layout()
        for cv in self.canvases:
            cv.draw_idle()

        self.report.configure(state="normal")
        self.report.delete("1.0", "end")
        if not b:
            self.report.insert("end", "Sem recomendação\n", "h"); self.report.insert("end", "\nNenhuma solução está incluída na análise.")
            self.report.configure(state="disabled")
            return
        self.report.insert("end", f"Recomendação: {b['nome']}\n", "h")
        self.report.insert("end", conclusao_texto(r) + "\n\n")
        self.report.insert("end", "Ficha de cada solução\n", "h2")
        for o in r["ranked"]:
            self.report.insert("end", f"#{o['rank']} {o['nome']}\n", "b")
            self.report.insert("end", ficha_texto(o, r) + "\n\n")
        self.report.insert("end", "Sensibilidade (±20% em cada parâmetro)\n", "h2")
        if r["sens"]:
            for l in r["sens"]:
                self.report.insert("end", f"{'★ ' if l['muda'] else '• '}{l['label']}: economia entre {brl(min(l['lo'], l['hi']))} "
                                          f"e {brl(max(l['lo'], l['hi']))}{' — muda a recomendação' if l['muda'] else ''}\n")
        else:
            self.report.insert("end", "Nenhum parâmetro altera a economia em ±20%.\n")
        docs = listar_documentos()
        n_ok = sum(1 for d in docs if d["arquivo"])
        self.report.insert("end", f"\nDocumentos do projeto: {n_ok} arquivo(s) cadastrado(s) na aba 06 · Documentos.\n")
        self.report.configure(state="disabled")

    # ----- cenários -----
    def _apply(self, src):
        clean = sanitize(src)
        val = {**DEFAULTS, **clean}
        for f in FIELDS:
            x = val[f[0]]
            self.vars[f[0]].set(str(int(x)) if f[7] else nfmt(x, 4).replace(".", "").rstrip("0").rstrip(","))
        for s in SOLS:
            self.vars["on_" + s["k"]].set(bool(val["on_" + s["k"]]))
        self.vars["criterio"].set(CRITERIOS.get(val["criterio"], CRITERIOS["econ"])[0])
        return clean

    def _load_last(self):
        try:
            obj = json.loads(last_scenario_path().read_text(encoding="utf-8"))
            self._apply(obj.get("parametros", obj))
            self.cenario_nome = obj.get("nome", "")
        except (OSError, ValueError, AttributeError):
            pass

    def _save_last(self):
        try:
            last_scenario_path().write_text(json.dumps({"versao": VERSION, "nome": self.cenario_nome,
                                                        "parametros": self.result["v"]}, ensure_ascii=False), encoding="utf-8")
        except OSError:
            logging.exception("Falha ao salvar o último cenário")

    def reset(self):
        if messagebox.askyesno("Restaurar padrões", "Substituir todos os valores pelos padrões?"):
            self._apply(DEFAULTS); self.cenario_nome = ""; self.calculate(True)

    def save_scenario(self):
        if not self.calculate(True):
            return
        nome = simpledialog.askstring("Salvar cenário", "Nome do cenário:", parent=self,
                                      initialvalue=self.cenario_nome or "Cenário " + datetime.now().strftime("%d-%m-%Y"))
        if not nome:
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Cenário JSON", "*.json")],
                                            initialfile=safe_name(nome) + ".json")
        if path:
            self.cenario_nome = nome
            self.export_json(path, quiet=True)
            self.set_status(f"Cenário “{nome}” salvo em {path}")

    def open_scenario(self):
        path = filedialog.askopenfilename(filetypes=[("Cenário JSON", "*.json")])
        if not path:
            return
        try:
            obj = json.loads(Path(path).read_text(encoding="utf-8"))
            params = obj.get("parametros", obj) if isinstance(obj, dict) else None
            if not sanitize(params):
                raise ValueError("o arquivo não contém parâmetros do simulador")
            self._apply(params)
            self.cenario_nome = obj.get("nome", Path(path).stem)
            self.calculate(True)
            if str(obj.get("versao", "")) != VERSION:
                messagebox.showinfo("Cenário de versão anterior",
                                    "Cenário importado. Campos que não existiam na versão do arquivo "
                                    "(ocupação, pé-direito, taxa de avaria, horizonte, vida útil) receberam os valores padrão.")
        except (OSError, ValueError) as e:
            messagebox.showerror("Erro", f"Não foi possível abrir o cenário.\n\n{e}")

    # ----- exportações -----
    def _write(self, path, fn, quiet):
        try:
            fn(path)
            return True
        except PermissionError:
            msg = f"Não foi possível gravar:\n{path}\n\nSe o arquivo estiver aberto em outro programa (Excel, leitor de PDF), feche-o e tente de novo."
        except OSError as e:
            msg = f"Não foi possível gravar:\n{path}\n\n{e}"
        logging.error(msg)
        if quiet == "raise":
            raise RuntimeError(msg)
        messagebox.showerror("Erro ao salvar", msg)
        return False

    def export_json(self, path=None, quiet=False):
        if not self.calculate(True):
            return
        if path is None:
            path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")],
                                                initialfile="cenario_uce2.json")
        if not path:
            return
        r = self.result
        obj = {"app": "Simulador Inteligente de Armazenagem – UCE II", "versao": VERSION, "nome": self.cenario_nome,
               "data": r["data"].isoformat(timespec="seconds"), "parametros": r["v"],
               "resultado": {"total_caixas": r["total"], "perda_mensal": r["perda_mes"], "perda_horizonte": r["perda_h"],
                             "recomendada": r["best"]["nome"] if r["best"] else None,
                             "solucoes": [{k: (None if isinstance(x, float) and not math.isfinite(x) else x)
                                           for k, x in o.items() if k != "curto"} for o in r["ranked"]]}}
        if self._write(path, lambda p: Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8"), quiet) and not quiet:
            self.set_status(f"JSON salvo em {path}")

    def export_csv(self, path=None, quiet=False):
        if not self.ensure_result():
            return
        if path is None:
            path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                                initialfile="resultado_uce2.csv")
        if not path:
            return
        r = self.result; v = r["v"]

        def escrever(p):
            with open(p, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["Simulador Inteligente de Armazenagem – UCE II", "v" + VERSION])
                w.writerow(["Cenário", self.cenario_nome or "—"]); w.writerow(["Gerado em", datetime.now().strftime("%d/%m/%Y %H:%M")])
                w.writerow(["Critério", CRITERIOS[v["criterio"]][0]]); w.writerow([])
                w.writerow(["PARÂMETROS", "Valor", "Unidade"])
                for key, label, unit, *_rest in FIELDS:
                    grupo = FIELD_BY_KEY[key][8]
                    pref = next((s["nome"] + " – " for s in SOLS if s["k"] == grupo), "")
                    w.writerow([pref + label, dec(v[key]), unit])
                w.writerow([]); w.writerow(["INDICADORES", "Valor"])
                for nome, x in [("Caixas por camada", r["por_camada"]), ("Camadas efetivas", r["camadas"]),
                                ("Total de caixas", r["total"]), ("Avarias por mês (caixas)", r["avarias_mes"]),
                                ("Perda mensal sem proteção (R$)", r["perda_mes"]), ("Perda no horizonte (R$)", r["perda_h"])]:
                    w.writerow([nome, dec(x)])
                w.writerow([])
                w.writerow(["Posição", "Solução", "Quantidade", "Investimento inicial (R$)", "Custo no horizonte (R$)",
                            "Proteção (%)", "Perda evitada (R$)", "Economia líquida (R$)", "ROI (%)", "Payback (meses)", "Custo por 1% (R$)"])
                for o in r["ranked"]:
                    w.writerow([o["rank"], o["nome"], dec(o["qtd"]), dec(o["inv"]), dec(o["custo_h"]), dec(o["r"] * 100),
                                dec(o["evitada"]), dec(o["econ"]), dec(o["roi"]),
                                "0" if o["payback"] == 0 else (dec(o["payback"]) if math.isfinite(o["payback"]) else "não se paga"),
                                dec(o["cb"])])

        if self._write(path, escrever, quiet) and not quiet:
            self.set_status(f"CSV salvo em {path}")

    def export_pngs(self, folder=None, quiet=False):
        if not self.ensure_result():
            return
        if folder is None:
            folder = filedialog.askdirectory(title="Pasta dos gráficos")
        if not folder:
            return

        def salvar(pasta):
            for fig, (_fn, _t, nome) in zip(self.figs, GRAFICOS):
                fig.savefig(Path(pasta) / nome, dpi=200, bbox_inches="tight", facecolor="white")

        if self._write(folder, salvar, quiet) and not quiet:
            messagebox.showinfo("Gráficos", f"{len(GRAFICOS)} gráficos PNG salvos em:\n{folder}")

    def secoes_escolhidas(self):
        return [sid for sid, _t in SECOES if self.secoes_vars[sid].get()]

    def _gerar(self, path, secoes, quiet):
        self.config(cursor="watch"); self.update_idletasks()
        try:
            return self._write(path, lambda p: gerar_pdf(p, self.result, self.cenario_nome, secoes, listar_documentos()), quiet)
        finally:
            self.config(cursor="")

    def export_pdf(self, path=None, quiet=False, secoes=None):
        if not self.ensure_result():
            return
        secoes = secoes or self.secoes_escolhidas()
        if not secoes:
            messagebox.showwarning("Relatórios", "Marque pelo menos um relatório na Central de relatórios."); return
        if path is None:
            path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                                initialfile="Relatorio_UCE_II.pdf")
        if not path:
            return
        if self._gerar(path, secoes, quiet) and not quiet:
            if messagebox.askyesno("Relatório", f"Relatório PDF gerado ({len(secoes)} relatório(s)):\n{path}\n\nAbrir agora?"):
                try:
                    open_path(path)
                except OSError:
                    pass

    def export_pdfs_separados(self, folder=None, quiet=False):
        if not self.ensure_result():
            return
        secoes = self.secoes_escolhidas() if not quiet else [s for s, _t in SECOES]
        if not secoes:
            messagebox.showwarning("Relatórios", "Marque pelo menos um relatório na Central de relatórios."); return
        if folder is None:
            folder = filedialog.askdirectory(title="Pasta para os relatórios em PDF")
        if not folder:
            return
        nomes = dict(SECOES)
        for i, sid in enumerate(secoes, 1):
            ordem = [s for s, _t in SECOES].index(sid) + 1
            arq = Path(folder) / f"{ordem:02d}_{slug(nomes[sid])}.pdf"
            if not self._gerar(arq, [sid], quiet):
                return
        if not quiet and messagebox.askyesno("Relatórios", f"{len(secoes)} PDF(s) gerado(s) em:\n{folder}\n\nAbrir a pasta?"):
            open_path(folder)

    def print_reports(self):
        if not self.ensure_result():
            return
        secoes = self.secoes_escolhidas()
        if not secoes:
            messagebox.showwarning("Relatórios", "Marque pelo menos um relatório na Central de relatórios."); return
        pasta = data_dir() / "impressao"; pasta.mkdir(exist_ok=True)
        path = pasta / f"Relatorio_UCE_II_{datetime.now():%Y%m%d_%H%M%S}.pdf"
        if not self._gerar(path, secoes, False):
            return
        if not messagebox.askyesno("Imprimir", f"Enviar {len(secoes)} relatório(s) para a impressora padrão do Windows?"):
            return
        try:
            imprimir_arquivo(path)
            self.set_status("Relatório enviado para a impressora padrão.")
        except OSError as e:
            messagebox.showwarning("Impressão", "Não há um leitor de PDF configurado para imprimir automaticamente. "
                                                f"O PDF será aberto: use Ctrl+P para imprimir.\n\n{e}")
            try:
                open_path(path)
            except OSError:
                pass

    def export_package(self):
        if not self.ensure_result():
            return
        base = filedialog.askdirectory(title="Escolha onde criar o pacote completo")
        if not base:
            return
        dest = Path(base) / ("UCE_II_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
        try:
            (dest / "graficos").mkdir(parents=True, exist_ok=True)
            (dest / "relatorios_separados").mkdir(exist_ok=True)
            self.export_json(dest / "cenario_uce2.json", quiet="raise")
            self.export_csv(dest / "resultado_uce2.csv", quiet="raise")
            self.export_pngs(dest / "graficos", quiet="raise")
            self.export_pdf(dest / "Relatorio_UCE_II_completo.pdf", quiet="raise", secoes=[s for s, _t in SECOES])
            self.export_pdfs_separados(dest / "relatorios_separados", quiet="raise")
        except (OSError, RuntimeError) as e:
            messagebox.showerror("Pacote incompleto", str(e)); return
        if messagebox.askyesno("Pacote completo", f"Arquivos gerados em:\n{dest}\n\nAbrir a pasta?"):
            open_path(dest)


# ===== Funções auxiliares =====
def sanitize(src):
    out = {}
    if not isinstance(src, dict):
        return out
    for f in FIELDS:
        x = src.get(f[0])
        try:
            if x is not None and x != "" and math.isfinite(float(x)):
                out[f[0]] = float(x)
        except (TypeError, ValueError):
            pass
    for s in SOLS:
        if isinstance(src.get("on_" + s["k"]), bool):
            out["on_" + s["k"]] = src["on_" + s["k"]]
    if src.get("criterio") in CRITERIOS:
        out["criterio"] = src["criterio"]
    return out

def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:60] or "relatorio"

def safe_name(s):
    return "".join(c if c.isalnum() or c in " -_" else "_" for c in s).strip()[:60] or "cenario"

def conclusao_texto(r):
    v, b = r["v"], r["best"]
    pb = ("retorno imediato" if b["payback"] == 0 else
          f"payback de {fmt_payback(b['payback'])}" if math.isfinite(b["payback"]) else "sem payback dentro da vida útil")
    compras = f" ({b['ciclos']} compras de {brl(b['inv'])})" if b["ciclos"] > 1 else f" (investimento de {brl(b['inv'])})"
    t = (f"Critério: {CRITERIOS[v['criterio']][0].lower()}. Em {v['horiz']} meses, com {r['total']} caixas e taxa de avaria "
         f"de {nfmt(v['taxa'], 1)}% ao mês, a perda sem proteção estimada é de {brl(r['perda_h'])}. "
         f"A solução recomendada custa {brl(b['custo_h'])} no período{compras}, reduz as avarias em {pct(b['r'] * 100)} "
         f"e gera economia líquida de {brl(b['econ'])}, com ROI de {pct(b['roi'])} e {pb}.")
    if b["econ"] <= 0:
        t += " Atenção: não há economia positiva no horizonte; do ponto de vista financeiro, não investir é a melhor opção."
    if r["best_econ"] is not b:
        t += f" Pelo critério de economia líquida, a escolha seria {r['best_econ']['nome']} ({brl(r['best_econ']['econ'])})."
    return t


def ficha_texto(o, r):
    hz = r["v"]["horiz"]
    linhas = [f"Posição no critério: {o['rank']}º · proteção de {pct(o['r'] * 100)}",
              f"Quantidade: {nfmt(o['qtd'], 0)} · investimento inicial {brl(o['inv'])} · vida útil {o['vida']} meses",
              f"Compras no horizonte: {o['ciclos']} · custo em {hz} meses: {brl(o['custo_h'])}",
              f"Perda evitada: {brl(o['evitada'])} · perda residual: {brl(o['residual'])}",
              f"Economia líquida: {brl(o['econ'])} · ROI: {pct(o['roi'])} · payback: {fmt_payback(o['payback'])} · "
              f"custo por 1%: {fmt_cb(o['cb'])}"]
    return "\n".join(linhas)


# ===== Relatório PDF =====
A4 = (8.27, 11.69)

def _pagina(titulo, subtitulo=""):
    fig = Figure(figsize=A4, facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.add_patch(Rectangle((0, .93), 1, .07, transform=ax.transAxes, color=NAVY))
    ax.add_patch(Rectangle((0, .926), 1, .004, transform=ax.transAxes, color=ORANGE))
    _logo(fig, .035, .935, .055)
    ax.text(.11, .958, titulo, color="white", fontsize=15, fontweight="bold", transform=ax.transAxes, va="center")
    if subtitulo:
        ax.text(.06, .9, subtitulo, fontsize=9.5, color=MUTED, transform=ax.transAxes)
    return fig, ax

_LOGO_CACHE = []
def _logo(fig, x, y, largura):
    """Desenha a logo original do simulador (arquivo sem nenhuma edição), só redimensionada para caber."""
    try:
        if not _LOGO_CACHE:
            _LOGO_CACHE.append(matplotlib.image.imread(str(resource_path("logo_simulador.jpg"))))
        ax = fig.add_axes([x, y, largura, largura * A4[0] / A4[1]], zorder=5)
        ax.imshow(_LOGO_CACHE[0], interpolation="lanczos"); ax.axis("off")
        return True
    except (OSError, ValueError, SyntaxError):
        return False

def _rodape(fig, n, cenario):
    fig.text(.06, .025, f"Simulador Inteligente de Armazenagem – UCE II · v{VERSION}" + (f" · {cenario}" if cenario else ""),
             fontsize=7.5, color=MUTED)
    fig.text(.94, .025, f"página {n}", fontsize=7.5, color=MUTED, ha="right")

def _sec_resumo(r, cenario):
    v, b = r["v"], r["best"]
    fig = Figure(figsize=A4, facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.add_patch(Rectangle((0, .84), 1, .16, transform=ax.transAxes, color=NAVY))
    ax.add_patch(Rectangle((0, .835), 1, .007, transform=ax.transAxes, color=ORANGE))
    x0 = .19 if _logo(fig, .05, .855, .11) else .07
    ax.text(x0, .935, "UCE II", color="#FF9D52", fontsize=13, fontweight="bold", transform=ax.transAxes)
    ax.text(x0, .895, "SIMULADOR INTELIGENTE DE ARMAZENAGEM", color="white", fontsize=17, fontweight="bold", transform=ax.transAxes)
    ax.text(x0, .862, "Relatório técnico de análise de soluções de armazenagem" + (f" · {cenario}" if cenario else ""),
            color="#DCE8F4", fontsize=9.5, transform=ax.transAxes)
    ax.text(.07, .785, "RESUMO DO CENÁRIO", fontsize=12, fontweight="bold", color=NAVY, transform=ax.transAxes)
    ax.text(.93, .785, f"Gerado em {datetime.now():%d/%m/%Y %H:%M}", fontsize=8, color=MUTED, ha="right", transform=ax.transAxes)
    cards = [(.07, "TOTAL DE CAIXAS", nfmt(r["total"], 0)), (.29, "AVARIAS / MÊS", nfmt(r["avarias_mes"], 1)),
             (.51, "PERDA / MÊS", brl_pdf(r["perda_mes"])), (.73, f"PERDA EM {v['horiz']} MESES", brl_pdf(r["perda_h"]))]
    for x, title, value in cards:
        ax.add_patch(FancyBboxPatch((x, .68), .19, .085, boxstyle="round,pad=0.008,rounding_size=0.01",
                                    transform=ax.transAxes, facecolor=PALE_BLUE, edgecolor=LINE))
        ax.text(x + .012, .738, title, fontsize=7, color=MUTED, fontweight="bold", transform=ax.transAxes)
        ax.text(x + .012, .697, value, fontsize=11.5, color=NAVY, fontweight="bold", transform=ax.transAxes)
    ax.text(.07, .62, "PARÂMETROS", fontsize=12, fontweight="bold", color=NAVY, transform=ax.transAxes)
    ax.add_patch(FancyBboxPatch((.07, .43), .86, .165, boxstyle="round,pad=0.012,rounding_size=0.012",
                                transform=ax.transAxes, facecolor=BG, edgecolor=LINE))
    pe = "sem limite" if v["pe"] <= 0 else f"{nfmt(v['pe'])} m"
    info = (f"Área do piso: {nfmt(v['area'])} m² · ocupação {nfmt(v['ocup'], 0)}% · área útil {nfmt(r['area_util'])} m²\n"
            f"Caixa: {nfmt(v['larg'])} × {nfmt(v['comp'])} × {nfmt(v['alt'])} m · {r['por_camada']} caixas por camada\n"
            f"Empilhamento máximo: {v['pilha']} · pé-direito útil: {pe} · camadas efetivas: {r['camadas']}\n"
            f"Taxa de avaria: {nfmt(v['taxa'], 1)}% ao mês · valor por caixa danificada: {brl_pdf(v['vperd'])}\n"
            f"Horizonte: {v['horiz']} meses · critério: {CRITERIOS[v['criterio']][0].lower()}")
    ax.text(.095, .575, info, fontsize=9.5, color=INK, va="top", linespacing=1.75, transform=ax.transAxes)
    ax.text(.07, .375, "SOLUÇÃO RECOMENDADA", fontsize=12, fontweight="bold", color=NAVY, transform=ax.transAxes)
    ruim = b["econ"] <= 0
    ax.add_patch(FancyBboxPatch((.07, .185), .86, .165, boxstyle="round,pad=0.014,rounding_size=0.014",
                                transform=ax.transAxes, facecolor=PALE_RED if ruim else PALE_ORANGE,
                                edgecolor=RED if ruim else ORANGE, linewidth=1.2))
    ax.text(.095, .31, b["nome"], fontsize=15, fontweight="bold", color=BLUE, transform=ax.transAxes)
    ax.text(.095, .272, f"Investimento inicial: {brl_pdf(b['inv'])}   ·   custo em {v['horiz']} meses: {brl_pdf(b['custo_h'])}",
            fontsize=9.5, transform=ax.transAxes)
    ax.text(.095, .243, f"Proteção: {pct(b['r'] * 100)}   ·   ROI: {pct(b['roi'])}   ·   payback: {fmt_payback(b['payback'])}",
            fontsize=9.5, transform=ax.transAxes)
    ax.text(.095, .212, f"Perda evitada: {brl_pdf(b['evitada'])}   ·   economia líquida: {brl_pdf(b['econ'])}",
            fontsize=9.5, color=RED if ruim else GREEN, fontweight="bold", transform=ax.transAxes)
    ax.text(.07, .12, "Faculdade SENAI • Contagem (MG) • Tecnólogo em Ciência de Dados", fontsize=8.5, color=MUTED, transform=ax.transAxes)
    ax.text(.07, .095, f"Equipe: {EQUIPE}", fontsize=8.5, color=MUTED, transform=ax.transAxes)
    ax.text(.07, .07, f"Orientadora: {ORIENTADORA}", fontsize=8.5, color=MUTED, transform=ax.transAxes)
    return [fig]

def _sec_comparativo(r, cenario):
    v, b = r["v"], r["best"]
    fig, ax = _pagina("COMPARATIVO DAS SOLUÇÕES", f"Ordenado por: {CRITERIOS[v['criterio']][0].lower()}")
    rows = [[str(o["rank"]), o["curto"], brl_pdf(o["inv"]), brl_pdf(o["custo_h"]), pct(o["r"] * 100), brl_pdf(o["evitada"]),
             brl_pdf(o["econ"]), pct(o["roi"]), fmt_payback(o["payback"]).replace(" meses", " m")] for o in r["ranked"]]
    altura = .07 + .075 * len(rows)
    table = ax.table(cellText=rows, colLabels=["#", "Solução", "Investim.", f"Custo {v['horiz']} m", "Proteção",
                                               "Perda evitada", "Econ. líquida", "ROI", "Payback"],
                     bbox=[.03, .86 - altura, .94, altura], cellLoc="center", colLoc="center",
                     colWidths=[.04, .15, .12, .12, .09, .13, .13, .09, .11])
    table.auto_set_font_size(False); table.set_fontsize(7.4)
    for (rr, cc), cell in table.get_celld().items():
        cell.set_edgecolor(LINE)
        if rr == 0:
            cell.set_facecolor(NAVY); cell.get_text().set_color("white"); cell.get_text().set_weight("bold")
        else:
            o = r["ranked"][rr - 1]
            cell.set_facecolor(PALE_BLUE if o is b else "white")
            if cc == 6:
                cell.get_text().set_color(GREEN if o["econ"] > 0 else RED)
            if o is b and cc == 1:
                cell.get_text().set_weight("bold"); cell.get_text().set_color(BLUE)
    y = .86 - altura - .05
    ax.text(.06, y, "LEITURA DO RESULTADO", fontsize=12, fontweight="bold", color=NAVY, transform=ax.transAxes)
    linhas = textwrap.wrap(conclusao_texto(r).replace("$", r"\$"), width=100, break_long_words=False)
    for tipo, a in alertas(r):
        if tipo in ("bad", "warn"):
            linhas += [""] + textwrap.wrap("Aviso: " + a.replace("$", r"\$"), width=100, break_long_words=False)
    alt_caixa = .03 + .019 * len(linhas)
    ax.add_patch(FancyBboxPatch((.06, y - .02 - alt_caixa), .88, alt_caixa, boxstyle="round,pad=0.012,rounding_size=0.012",
                                transform=ax.transAxes, facecolor=PALE_GREEN, edgecolor="#B7D9C3"))
    ax.text(.085, y - .035, "\n".join(linhas), fontsize=9, color="#173D26", va="top", linespacing=1.5, transform=ax.transAxes)
    y = y - .07 - alt_caixa
    ax.text(.06, y, "CRITÉRIOS DE CÁLCULO", fontsize=11, fontweight="bold", color=NAVY, transform=ax.transAxes)
    formulas = [
        "Caixas por camada = piso(área × ocupação ÷ (largura × comprimento)); camadas = mín(empilhamento, piso(pé-direito ÷ altura))",
        "Perda no horizonte = total de caixas × taxa de avaria × valor por caixa × meses",
        "Custo no horizonte = investimento × teto(meses ÷ vida útil)  (a solução é recomprada a cada vida útil)",
        "Economia líquida = perda evitada − custo no horizonte;  ROI = economia ÷ custo × 100",
        "Payback = investimento ÷ perda evitada por mês  (“não se paga” quando passa da vida útil)",
        "Custo por 1% = custo no horizonte ÷ redução de danos (pontos percentuais)",
    ]
    for i, t in enumerate(formulas):
        ax.text(.06, y - .03 - i * .024, "• " + t, fontsize=7.8, color=MUTED, transform=ax.transAxes)
    return [fig]

def _sec_graficos(titulo, sub, g1, g2):
    def fazer(r, cenario):
        fig, _ax = _pagina(titulo, sub)
        g1(fig.add_axes([.11, .52, .82, .32]), r)
        esquerda = .27 if g2 is chart_tornado else .11   # rótulos do tornado ficam à esquerda
        g2(fig.add_axes([esquerda, .1, .93 - esquerda, .32]), r)
        return [fig]
    return fazer

def _sec_solucoes(r, cenario):
    figs = []
    for o in r["ranked"]:
        fig, ax = _pagina(f"FICHA · {o['nome'].upper()}", f"{o['rank']}º pelo critério: {CRITERIOS[r['v']['criterio']][0].lower()}"
                          + ("  ·  RECOMENDADA" if o is r["best"] else ""))
        dados = [["Proteção (redução de danos)", pct(o["r"] * 100)], ["Quantidade", nfmt(o["qtd"], 0)],
                 ["Investimento inicial", brl_pdf(o["inv"])], ["Vida útil", f"{o['vida']} meses"],
                 ["Compras no horizonte", str(o["ciclos"])], [f"Custo em {r['v']['horiz']} meses", brl_pdf(o["custo_h"])],
                 ["Perda evitada", brl_pdf(o["evitada"])], ["Perda residual", brl_pdf(o["residual"])],
                 ["Economia líquida", brl_pdf(o["econ"])], ["ROI", pct(o["roi"])],
                 ["Payback", fmt_payback(o["payback"])], ["Custo por 1% de proteção", fmt_cb(o["cb"]).replace("$", r"\$")]]
        t = ax.table(cellText=dados, colLabels=["Indicador", "Valor"], bbox=[.12, .5, .76, .37], cellLoc="left", colLoc="left",
                     colWidths=[.55, .45])
        t.auto_set_font_size(False); t.set_fontsize(9)
        for (rr, cc), cell in t.get_celld().items():
            cell.set_edgecolor(LINE)
            if rr == 0:
                cell.set_facecolor(NAVY); cell.get_text().set_color("white"); cell.get_text().set_weight("bold")
            elif rr == 9:
                cell.set_facecolor(PALE_GREEN if o["econ"] > 0 else PALE_RED)
        chart_fluxo(fig.add_axes([.11, .1, .82, .32]), r, apenas=o["k"])
        figs.append(fig)
    return figs

def _sec_documentos(r, cenario, docs):
    docs = docs or []
    linhas = [[str(i), d["titulo"][:48], d["categoria"][:26], (d["nome_original"] or "aguardando arquivo")[:40],
               tamanho_legivel(d["tamanho"]) if d["arquivo"] else "—", (d["atualizado_em"] or "")[:10]]
              for i, d in enumerate(docs, 1)]
    por_pagina = 30
    figs = []
    for ini in range(0, max(1, len(linhas)), por_pagina):
        bloco = linhas[ini:ini + por_pagina]
        n_ok = sum(1 for d in docs if d["arquivo"])
        fig, ax = _pagina("DOCUMENTOS DO PROJETO", f"{n_ok} arquivo(s) armazenado(s) na biblioteca do programa")
        if not bloco:
            ax.text(.5, .6, "Nenhum documento cadastrado.", ha="center", color=MUTED, transform=ax.transAxes)
        else:
            alt = .025 * (len(bloco) + 1)
            t = ax.table(cellText=[[c.replace("$", r"\$") for c in l] for l in bloco],
                         colLabels=["#", "Título", "Categoria", "Arquivo", "Tamanho", "Data"],
                         bbox=[.04, .86 - alt, .92, alt], cellLoc="left", colLoc="left",
                         colWidths=[.05, .32, .2, .26, .08, .09])
            t.auto_set_font_size(False); t.set_fontsize(7.2)
            for (rr, cc), cell in t.get_celld().items():
                cell.set_edgecolor(LINE)
                if rr == 0:
                    cell.set_facecolor(NAVY); cell.get_text().set_color("white"); cell.get_text().set_weight("bold")
        figs.append(fig)
    return figs

SECAO_FUNCOES = {
    "resumo": _sec_resumo,
    "comparativo": _sec_comparativo,
    "financeiro": _sec_graficos("ANÁLISE GRÁFICA", "Comparação financeira das alternativas", chart_custo_evitada, chart_economia),
    "eficiencia": _sec_graficos("EFICIÊNCIA E IMPACTO", "Custo da proteção e perda que continua acontecendo", chart_cb, chart_residual),
    "retorno": _sec_graficos("RETORNO E MULTICRITÉRIO", "Tempo de retorno e desempenho relativo em cinco critérios", chart_payback, chart_multicriterio),
    "evolucao": _sec_graficos("EVOLUÇÃO E SENSIBILIDADE", "Resultado acumulado mês a mês e efeito de ±20% em cada parâmetro", chart_fluxo, chart_tornado),
    "solucoes": _sec_solucoes,
}

def gerar_pdf(path, r, cenario="", secoes=None, docs=None):
    secoes = secoes or [s for s, _t in SECOES]
    if r.get("sens") is None:
        r["sens"] = sensibilidade(r)
    n = 0
    with PdfPages(path) as pdf:
        for sid in secoes:
            figs = _sec_documentos(r, cenario, docs) if sid == "documentos" else SECAO_FUNCOES[sid](r, cenario)
            for fig in figs:
                n += 1
                _rodape(fig, n, cenario)
                pdf.savefig(fig)
        info = pdf.infodict()
        info["Title"] = "Relatório – Simulador Inteligente de Armazenagem UCE II"
        info["Author"] = "Equipe UCE II – Faculdade SENAI Contagem"
    return n


# ===== Inicialização =====
def setup_logging():
    try:
        logging.basicConfig(filename=str(data_dir() / "simulador.log"), level=logging.INFO, encoding="utf-8",
                            format="%(asctime)s %(levelname)s %(message)s")
    except OSError:
        logging.basicConfig(level=logging.INFO)

def enable_dpi_awareness():
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass

def selftest(pasta):
    pasta = Path(pasta).resolve(); pasta.mkdir(parents=True, exist_ok=True)
    os.environ["LOCALAPPDATA"] = str(pasta / "dados")   # não mexe nos dados reais do usuário
    app = Simulator(); app.withdraw(); app.update()
    linhas = []
    try:
        assert app.calculate(show_errors=False), "cálculo inicial falhou"
        app._apply(DEFAULTS); assert app.calculate(show_errors=False)
        r = app.result
        linhas.append(f"total={r['total']} perda_h={r['perda_h']:.2f} best={r['best']['nome']} econ={r['best']['econ']:.2f}")
        linhas.append(f"sensibilidade={len(r['sens'])} linhas")
        # biblioteca: 12 documentos de tipos variados
        origem = pasta / "origem"; origem.mkdir(exist_ok=True)
        for i in range(12):
            ext = [".pdf", ".docx", ".xlsx", ".pptx", ".png", ".txt"][i % 6]
            f = origem / f"documento_teste_{i + 1:02d}{ext}"
            f.write_bytes(b"%PDF-1.4\n%teste\n" if ext == ".pdf" else b"teste")
            adicionar_documento(f)
        substituir_arquivo(obter_documento(tipo="mapa_empatia")["id"], origem / "documento_teste_01.pdf")
        app.atualizar_documentos()
        docs = listar_documentos()
        n_arq = sum(1 for d in docs if d["arquivo"] and caminho_documento(d).exists())
        remover_documento(docs[-1]["id"])
        linhas.append(f"documentos: {len(docs)} registros, {n_arq} arquivos; após remover 1: {len(listar_documentos())} registros")
        app.export_json(pasta / "teste.json", quiet="raise")
        app.export_csv(pasta / "teste.csv", quiet="raise")
        app.export_pngs(pasta, quiet="raise")
        paginas = gerar_pdf(pasta / "teste_completo.pdf", app.result, "Autoteste", None, listar_documentos())
        linhas.append(f"pdf completo: {paginas} páginas")
        (pasta / "separados").mkdir(exist_ok=True)
        app.export_pdfs_separados(pasta / "separados", quiet="raise")
        linhas.append(f"pdfs separados: {len(list((pasta / 'separados').glob('*.pdf')))}")
        for crit in CRITERIOS:
            w = dict(DEFAULTS, criterio=crit); m = modelo(w)
            linhas.append(f"criterio {crit}: {m['best']['nome']}")
        linhas.append("OK")
        codigo = 0
    except Exception:
        linhas.append(traceback.format_exc()); codigo = 1
    finally:
        app.destroy()
    (pasta / "selftest.txt").write_text("\n".join(linhas), encoding="utf-8")
    return codigo

def main():
    setup_logging()
    enable_dpi_awareness()
    if "--selftest" in sys.argv:
        i = sys.argv.index("--selftest")
        pasta = sys.argv[i + 1] if len(sys.argv) > i + 1 else str(data_dir() / "selftest")
        sys.exit(selftest(pasta))
    logging.info("Iniciando v%s", VERSION)
    Simulator().mainloop()


if __name__ == "__main__":
    main()
