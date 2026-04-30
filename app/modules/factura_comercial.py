"""
factura_comercial.py
====================
Ventana de Factura Comercial para envíos internacionales.
- Hasta 5 líneas de productos
- Vista previa PDF antes de enviar
- Genera PDF descargable para el cliente
"""
import tkinter as tk
from tkinter import messagebox, filedialog
import os, platform, subprocess, tempfile

# ── Paleta ────────────────────────────────────────────────────────
C = {
    "bg": "#0D0D0D", "card": "#1A1A1A", "accent": "#C9A84C",
    "accent2": "#E05C2A", "text": "#F5E6C8", "text_sub": "#9A8A6A",
    "green": "#388E3C", "border": "#3A3020", "int_bg": "#0f1f0f",
    "int_header": "#81C784",
}
FONT_TITLE  = ("Segoe UI", 12, "bold")
FONT_BODY   = ("Segoe UI", 9)
FONT_SMALL  = ("Segoe UI", 8)
FONT_HEADER = ("Segoe UI", 8, "bold")

# Países más comunes (código ISO → nombre)
PAISES = {
    "MX": "México", "US": "Estados Unidos", "CA": "Canadá",
    "CN": "China", "ES": "España", "DE": "Alemania",
    "FR": "Francia", "GB": "Reino Unido", "JP": "Japón",
    "BR": "Brasil", "CO": "Colombia", "AR": "Argentina",
    "CL": "Chile", "IT": "Italia", "KR": "Corea del Sur",
    "IN": "India", "AU": "Australia", "NL": "Países Bajos",
    "OTHER": "Otro",
}

PURPOSES_ES = {
    "personal": "Uso Personal",
    "commercial": "Uso Comercial",
    "gift": "Regalo",
    "sample": "Muestra sin valor comercial",
    "return": "Devolución",
}


# ─────────────────────────────────────────────────────────────────
class VentanaFacturaComercial(tk.Toplevel):
    """
    Ventana modal para capturar los productos de la factura comercial.
    Callback: on_confirm(productos: list[dict]) donde cada dict tiene:
        description_en, description_es, hs_code, quantity,
        unit_price, weight, country_of_origin
    """

    MAX_PRODUCTOS = 5

    def __init__(self, parent, remitente: dict, destinatario: dict,
                 shipment_purpose: str = "personal",
                 contenido_sugerido: str = "",
                 valor_sugerido: float = 100.0,
                 peso_total: float = 1.0,
                 on_confirm=None):
        super().__init__(parent)
        self.title("📋  Factura Comercial — Envío Internacional")
        self.geometry("780x640")
        self.resizable(True, True)
        self.configure(bg=C["bg"])
        self.grab_set()
        self.focus_set()

        self.remitente     = remitente
        self.destinatario  = destinatario
        self.purpose       = shipment_purpose
        self.peso_total    = peso_total
        self.on_confirm    = on_confirm
        self._filas        = []   # lista de dicts con StringVars por fila

        self._build_ui(contenido_sugerido, valor_sugerido, peso_total)

    # ── Construcción UI ──────────────────────────────────────────
    def _build_ui(self, contenido_sugerido, valor_sugerido, peso_total):
        # ── Encabezado ───────────────────────────────────────────
        hdr = tk.Frame(self, bg=C["int_bg"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="🌍  FACTURA COMERCIAL / COMMERCIAL INVOICE",
                 font=FONT_TITLE, bg=C["int_bg"],
                 fg=C["int_header"]).pack(side="left", padx=14, pady=10)
        tk.Label(hdr,
                 text=f"Propósito: {PURPOSES_ES.get(self.purpose, self.purpose)}",
                 font=FONT_SMALL, bg=C["int_bg"],
                 fg=C["text_sub"]).pack(side="right", padx=14)

        # ── Datos remitente / destinatario ───────────────────────
        info_f = tk.Frame(self, bg=C["card"])
        info_f.pack(fill="x", padx=8, pady=(6, 0))
        info_f.columnconfigure(0, weight=1)
        info_f.columnconfigure(1, weight=1)

        self._info_col(info_f, "EXPORTADOR / REMITENTE", self.remitente, 0)
        self._info_col(info_f, "IMPORTADOR / DESTINATARIO", self.destinatario, 1)

        # ── Tabla de productos ───────────────────────────────────
        tabla_card = tk.Frame(self, bg=C["card"], relief="flat")
        tabla_card.pack(fill="both", expand=True, padx=8, pady=6)

        tk.Label(tabla_card,
                 text="DESCRIPCIÓN DE MERCANCÍAS",
                 font=FONT_HEADER, bg=C["card"],
                 fg=C["accent"]).pack(anchor="w", padx=10, pady=(8, 4))

        # Cabeceras
        hdr_f = tk.Frame(tabla_card, bg="#2a2a2a")
        hdr_f.pack(fill="x", padx=6)
        headers = [
            ("Descripción (español)", 22),
            ("Description (English)", 22),
            ("HS Code", 10),
            ("Cant.", 5),
            ("P.Unit $", 8),
            ("Peso kg", 7),
            ("País orig.", 9),
        ]
        for txt, w in headers:
            tk.Label(hdr_f, text=txt, width=w, anchor="w",
                     bg="#2a2a2a", fg=C["text_sub"],
                     font=FONT_SMALL).pack(side="left", padx=2, pady=3)

        # Contenedor scrollable para filas
        self._tabla_frame = tk.Frame(tabla_card, bg=C["card"])
        self._tabla_frame.pack(fill="both", expand=True, padx=6)

        # Agregar primera fila pre-cargada con el contenido sugerido
        self._agregar_fila(
            desc_es=contenido_sugerido,
            desc_en="",
            cantidad=1,
            precio=valor_sugerido,
            peso=self.peso_total,
        )

        # Botón agregar fila
        btn_f = tk.Frame(tabla_card, bg=C["card"])
        btn_f.pack(fill="x", padx=6, pady=(4, 8))
        self._btn_agregar = tk.Button(
            btn_f, text="＋  Agregar producto",
            font=FONT_SMALL, bg="#2a3a2a", fg=C["int_header"],
            relief="flat", cursor="hand2", padx=8, pady=3,
            command=self._agregar_fila
        )
        self._btn_agregar.pack(side="left")
        tk.Label(btn_f, text=f"(máximo {self.MAX_PRODUCTOS} productos)",
                 font=FONT_SMALL, bg=C["card"],
                 fg=C["text_sub"]).pack(side="left", padx=8)

        # ── Totales ──────────────────────────────────────────────
        tot_f = tk.Frame(self, bg=C["card"])
        tot_f.pack(fill="x", padx=8, pady=(0, 4))
        tk.Label(tot_f, text="Total declarado USD:",
                 font=FONT_BODY, bg=C["card"],
                 fg=C["text_sub"]).pack(side="left", padx=14)
        self.lbl_total = tk.Label(tot_f, text="$ 0.00",
                                  font=("Segoe UI", 11, "bold"),
                                  bg=C["card"], fg=C["accent"])
        self.lbl_total.pack(side="left")
        tk.Label(tot_f, text="USD",
                 font=FONT_SMALL, bg=C["card"],
                 fg=C["text_sub"]).pack(side="left", padx=4)

        # ── Botones acción ───────────────────────────────────────
        act_f = tk.Frame(self, bg=C["bg"])
        act_f.pack(fill="x", padx=8, pady=8)

        tk.Button(act_f, text="✖  Cancelar",
                  font=FONT_BODY, bg="#333", fg="#aaa",
                  relief="flat", cursor="hand2", padx=12, pady=6,
                  command=self.destroy).pack(side="right", padx=4)

        tk.Button(act_f, text="📄  Vista Previa PDF",
                  font=FONT_BODY, bg="#1a3a4a", fg="#64B5F6",
                  relief="flat", cursor="hand2", padx=12, pady=6,
                  command=self._vista_previa).pack(side="right", padx=4)

        tk.Button(act_f, text="✔  Confirmar y Generar Guía",
                  font=("Segoe UI", 10, "bold"),
                  bg=C["accent"], fg="#000",
                  relief="flat", cursor="hand2", padx=14, pady=6,
                  command=self._confirmar).pack(side="right", padx=4)

    def _info_col(self, parent, titulo, datos, col):
        f = tk.Frame(parent, bg=C["card"])
        f.grid(row=0, column=col, sticky="nsew", padx=(8 if col == 0 else 4, 4 if col == 0 else 8), pady=6)
        tk.Label(f, text=titulo, font=FONT_HEADER,
                 bg=C["card"], fg=C["text_sub"]).pack(anchor="w", pady=(4, 2))
        nombre = datos.get("nombre", datos.get("empresa", ""))
        ciudad = datos.get("ciudad", "")
        estado = datos.get("estado", "")
        pais   = datos.get("pais", "MX")
        tk.Label(f, text=nombre, font=("Segoe UI", 9, "bold"),
                 bg=C["card"], fg=C["text"]).pack(anchor="w")
        tk.Label(f, text=f"{ciudad}, {estado}  {pais}",
                 font=FONT_SMALL, bg=C["card"],
                 fg=C["text_sub"]).pack(anchor="w")

    # ── Tabla dinámica ───────────────────────────────────────────
    def _agregar_fila(self, desc_es="", desc_en="", hs="",
                      cantidad=1, precio=0.0, peso=0.5):
        if len(self._filas) >= self.MAX_PRODUCTOS:
            messagebox.showwarning("Límite", f"Máximo {self.MAX_PRODUCTOS} productos",
                                   parent=self)
            return

        idx  = len(self._filas)
        fila = tk.Frame(self._tabla_frame,
                        bg="#1e1e1e" if idx % 2 == 0 else "#222222")
        fila.pack(fill="x", pady=1)

        # StringVars
        v_desc_es  = tk.StringVar(value=desc_es)
        v_desc_en  = tk.StringVar(value=desc_en)
        v_hs       = tk.StringVar(value=hs)
        v_cant     = tk.StringVar(value=str(cantidad))
        v_precio   = tk.StringVar(value=str(precio))
        v_peso     = tk.StringVar(value=str(peso))
        v_pais     = tk.StringVar(value="MX")

        entry_cfg = dict(font=FONT_BODY, relief="solid", bd=1,
                         bg="#111", fg=C["text"], insertbackground=C["text"])

        tk.Entry(fila, textvariable=v_desc_es,  width=22, **entry_cfg).pack(side="left", padx=2, pady=2)
        tk.Entry(fila, textvariable=v_desc_en,  width=22, **entry_cfg).pack(side="left", padx=2)
        tk.Entry(fila, textvariable=v_hs,       width=10, **entry_cfg).pack(side="left", padx=2)
        tk.Entry(fila, textvariable=v_cant,     width=5,  **entry_cfg).pack(side="left", padx=2)
        tk.Entry(fila, textvariable=v_precio,   width=8,  **entry_cfg).pack(side="left", padx=2)
        tk.Entry(fila, textvariable=v_peso,     width=7,  **entry_cfg).pack(side="left", padx=2)

        # Dropdown país origen
        pais_cb = ttk.Combobox(fila, textvariable=v_pais,
                               values=list(PAISES.keys()),
                               width=8, font=FONT_SMALL, state="readonly")
        pais_cb.pack(side="left", padx=2)

        # Botón eliminar (no para la primera fila)
        if idx > 0:
            tk.Button(fila, text="✕", font=FONT_SMALL,
                      bg="#3a0000", fg="#ff6666", relief="flat",
                      cursor="hand2", padx=4,
                      command=lambda f=fila, i=idx: self._eliminar_fila(f, i)
                      ).pack(side="left", padx=2)

        # Rastrear cambios para actualizar total
        for v in (v_cant, v_precio):
            v.trace_add("write", lambda *_: self._actualizar_total())

        row_data = {
            "frame": fila, "v_desc_es": v_desc_es, "v_desc_en": v_desc_en,
            "v_hs": v_hs, "v_cant": v_cant, "v_precio": v_precio,
            "v_peso": v_peso, "v_pais": v_pais,
        }
        self._filas.append(row_data)
        self._actualizar_total()

        # Ocultar botón agregar si llegamos al máximo
        if len(self._filas) >= self.MAX_PRODUCTOS:
            self._btn_agregar.config(state="disabled")

    def _eliminar_fila(self, frame, idx):
        frame.destroy()
        self._filas = [f for f in self._filas if f["frame"].winfo_exists()]
        self._btn_agregar.config(state="normal")
        self._actualizar_total()

    def _actualizar_total(self):
        total = 0.0
        for row in self._filas:
            try:
                cant  = float(row["v_cant"].get() or 0)
                precio = float(row["v_precio"].get() or 0)
                total += cant * precio
            except ValueError:
                pass
        self.lbl_total.config(text=f"$ {total:,.2f}")

    # ── Recopilar datos ──────────────────────────────────────────
    def _get_productos(self):
        """Retorna lista de dicts con los productos válidos."""
        productos = []
        for row in self._filas:
            desc_es = row["v_desc_es"].get().strip()
            desc_en = row["v_desc_en"].get().strip() or desc_es
            if not desc_es and not desc_en:
                continue
            try:
                cant  = max(1, int(float(row["v_cant"].get() or 1)))
                precio = max(0.01, float(row["v_precio"].get() or 1))
                peso   = max(0.01, float(row["v_peso"].get() or 0.5))
            except ValueError:
                cant, precio, peso = 1, 1.0, 0.5
            productos.append({
                "description_es":   desc_es,
                "description_en":   desc_en or desc_es,
                "hs_code":          row["v_hs"].get().strip() or "9999.99",
                "quantity":         cant,
                "unit_price":       precio,
                "price":            round(cant * precio, 2),
                "weight":           peso,
                "country_of_origin": row["v_pais"].get().strip() or "MX",
                "country_code":     row["v_pais"].get().strip() or "MX",
            })
        return productos

    # ── Vista previa PDF ─────────────────────────────────────────
    def _vista_previa(self):
        productos = self._get_productos()
        if not productos:
            messagebox.showwarning("Aviso",
                "Agrega al menos un producto con descripción", parent=self)
            return
        try:
            ruta = generar_pdf_factura(
                remitente=self.remitente,
                destinatario=self.destinatario,
                productos=productos,
                purpose=self.purpose,
            )
            # Abrir con visor del sistema
            if platform.system() == "Windows":
                os.startfile(ruta)
            elif platform.system() == "Darwin":
                subprocess.run(["open", ruta])
            else:
                subprocess.run(["xdg-open", ruta])
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el PDF:\n{e}", parent=self)

    # ── Confirmar ────────────────────────────────────────────────
    def _confirmar(self):
        productos = self._get_productos()
        if not productos:
            messagebox.showwarning("Aviso",
                "Agrega al menos un producto con descripción", parent=self)
            return

        # Guardar PDF de la factura
        try:
            ruta_pdf = generar_pdf_factura(
                remitente=self.remitente,
                destinatario=self.destinatario,
                productos=productos,
                purpose=self.purpose,
            )
        except Exception:
            ruta_pdf = None

        self.destroy()
        if self.on_confirm:
            self.on_confirm(productos, ruta_pdf)


# ─────────────────────────────────────────────────────────────────
# Importar ttk aquí para el Combobox (necesita estar después de la clase)
from tkinter import ttk


# ─────────────────────────────────────────────────────────────────
def generar_pdf_factura(remitente: dict, destinatario: dict,
                        productos: list, purpose: str = "personal",
                        ruta_pdf: str = None) -> str:
    """
    Genera el PDF de la Factura Comercial.
    Retorna la ruta al PDF generado.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, Spacer, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    import datetime

    if ruta_pdf is None:
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "facturas")
        os.makedirs(data_dir, exist_ok=True)
        ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta_pdf = os.path.join(data_dir, f"factura_comercial_{ts}.pdf")

    doc = SimpleDocTemplate(
        ruta_pdf,
        pagesize=letter,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=12*mm, bottomMargin=12*mm,
    )

    styles = getSampleStyleSheet()
    s_title   = ParagraphStyle("title",   fontSize=14, fontName="Helvetica-Bold",
                                alignment=TA_CENTER, spaceAfter=4)
    s_sub     = ParagraphStyle("sub",     fontSize=9,  fontName="Helvetica",
                                alignment=TA_CENTER, textColor=colors.grey, spaceAfter=8)
    s_section = ParagraphStyle("section", fontSize=9,  fontName="Helvetica-Bold",
                                textColor=colors.HexColor("#1a5276"), spaceAfter=4)
    s_normal  = ParagraphStyle("normal",  fontSize=8,  fontName="Helvetica", spaceAfter=2)
    s_small   = ParagraphStyle("small",   fontSize=7,  fontName="Helvetica",
                                textColor=colors.grey)
    s_right   = ParagraphStyle("right",   fontSize=9,  fontName="Helvetica-Bold",
                                alignment=TA_RIGHT)

    story = []
    W = letter[0] - 30*mm  # ancho útil

    # ── Título ──────────────────────────────────────────────────
    story.append(Paragraph("FACTURA COMERCIAL / COMMERCIAL INVOICE", s_title))
    now = datetime.datetime.now()
    story.append(Paragraph(
        f"Fecha / Date: {now.strftime('%d/%m/%Y')}  |  "
        f"Propósito / Purpose: {PURPOSES_ES.get(purpose, purpose)}",
        s_sub))
    story.append(HRFlowable(width="100%", thickness=1.5,
                             color=colors.HexColor("#C9A84C")))
    story.append(Spacer(1, 4*mm))

    # ── Exportador / Importador ──────────────────────────────────
    def _addr_lines(d):
        lines = []
        lines.append(f"<b>{d.get('nombre', d.get('empresa',''))}</b>")
        if d.get("calle"):
            lines.append(d["calle"] + (" " + d.get("num_interior","")).strip())
        col = d.get("colonia","")
        ciu = d.get("ciudad","")
        if col or ciu:
            lines.append(f"{col}, {ciu}".strip(", "))
        est = d.get("estado",""); cp = d.get("cp",""); pais = d.get("pais","MX")
        if est or cp:
            lines.append(f"{est}  C.P. {cp}  {pais}")
        if d.get("telefono"):
            lines.append(f"Tel: {d['telefono']}")
        if d.get("email"):
            lines.append(f"Email: {d['email']}")
        return "<br/>".join(lines)

    addr_data = [
        [Paragraph("<b>EXPORTADOR / EXPORTER</b>", s_section),
         Paragraph("<b>IMPORTADOR / IMPORTER</b>", s_section)],
        [Paragraph(_addr_lines(remitente),   s_normal),
         Paragraph(_addr_lines(destinatario), s_normal)],
    ]
    addr_table = Table(addr_data, colWidths=[W/2 - 3*mm, W/2 - 3*mm])
    addr_table.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0), colors.HexColor("#f0f0f0")),
        ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
        ("VALIGN",      (0,0), (-1,-1), "TOP"),
        ("PADDING",     (0,0), (-1,-1), 6),
        ("TOPPADDING",  (0,0), (-1,0), 4),
        ("BOTTOMPADDING",(0,0),(-1,0), 4),
    ]))
    story.append(addr_table)
    story.append(Spacer(1, 5*mm))

    # ── Tabla de productos ───────────────────────────────────────
    story.append(Paragraph("DESCRIPCIÓN DE MERCANCÍAS / DESCRIPTION OF GOODS", s_section))

    col_w = [W*0.22, W*0.22, W*0.10, W*0.06, W*0.10, W*0.10, W*0.10, W*0.10]
    prod_header = [
        Paragraph("<b>Descripción\n(Español)</b>",   s_small),
        Paragraph("<b>Description\n(English)</b>",   s_small),
        Paragraph("<b>HS Code</b>",                  s_small),
        Paragraph("<b>Qty</b>",                      s_small),
        Paragraph("<b>P.Unit\nUSD</b>",              s_small),
        Paragraph("<b>Total\nUSD</b>",               s_small),
        Paragraph("<b>Peso\nkg</b>",                 s_small),
        Paragraph("<b>País\nOrigen</b>",             s_small),
    ]
    prod_rows = [prod_header]
    total_usd   = 0.0
    total_peso  = 0.0
    total_items = 0
    for p in productos:
        subtotal = p.get("price", p["unit_price"] * p["quantity"])
        total_usd   += subtotal
        total_peso  += p["weight"] * p["quantity"]
        total_items += p["quantity"]
        prod_rows.append([
            Paragraph(p["description_es"], s_normal),
            Paragraph(p["description_en"], s_normal),
            Paragraph(p["hs_code"],        s_normal),
            Paragraph(str(p["quantity"]),  s_normal),
            Paragraph(f"${p['unit_price']:,.2f}", s_normal),
            Paragraph(f"${subtotal:,.2f}", s_normal),
            Paragraph(f"{p['weight']:.2f}", s_normal),
            Paragraph(p["country_of_origin"], s_normal),
        ])

    # Fila total
    prod_rows.append([
        Paragraph("<b>TOTAL</b>", s_normal), "", "",
        Paragraph(f"<b>{total_items}</b>", s_normal), "",
        Paragraph(f"<b>${total_usd:,.2f}</b>", s_normal),
        Paragraph(f"<b>{total_peso:.2f}</b>", s_normal), "",
    ])

    prod_table = Table(prod_rows, colWidths=col_w, repeatRows=1)
    prod_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  colors.HexColor("#1a5276")),
        ("TEXTCOLOR",     (0,0), (-1,0),  colors.white),
        ("BACKGROUND",    (0,-1),(-1,-1), colors.HexColor("#f5f5f5")),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN",         (3,1), (6,-1),  "RIGHT"),
        ("PADDING",       (0,0), (-1,-1), 5),
        ("ROWBACKGROUNDS",(0,1), (-1,-2), [colors.white, colors.HexColor("#f9f9f9")]),
    ]))
    story.append(prod_table)
    story.append(Spacer(1, 5*mm))

    # ── Resumen ──────────────────────────────────────────────────
    resumen_data = [
        ["Valor total declarado / Total Declared Value:",
         f"USD ${total_usd:,.2f}"],
        ["Peso total / Total Weight:",
         f"{total_peso:.2f} kg"],
        ["Moneda / Currency:",
         "USD – Dólares Americanos"],
        ["Incoterm:", "DAP (Delivered at Place)"],
    ]
    resumen_table = Table(resumen_data, colWidths=[W*0.6, W*0.4])
    resumen_table.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",  (1,0), (1,-1), "Helvetica"),
        ("FONTSIZE",  (0,0), (-1,-1), 8),
        ("ALIGN",     (1,0), (1,-1), "RIGHT"),
        ("PADDING",   (0,0), (-1,-1), 4),
        ("LINEBELOW", (0,-1),(-1,-1), 0.5, colors.grey),
    ]))
    story.append(resumen_table)
    story.append(Spacer(1, 8*mm))

    # ── Declaración y firma ──────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 3*mm))
    declaracion = (
        "El suscrito declara que la información contenida en esta factura comercial es verdadera y "
        "correcta y que el contenido de este envío está descrito correctamente. / "
        "The undersigned declares that the information contained in this commercial invoice is true "
        "and correct and that the contents of this shipment are accurately described."
    )
    story.append(Paragraph(declaracion, s_small))
    story.append(Spacer(1, 10*mm))

    firma_data = [
        [f"Firma / Signature: {'_'*35}",
         f"Fecha / Date: {now.strftime('%d / %m / %Y')}"],
        [f"Nombre / Name: {remitente.get('nombre','')}",
         f"Lugar / Place: {remitente.get('ciudad','')}"],
    ]
    firma_table = Table(firma_data, colWidths=[W*0.6, W*0.4])
    firma_table.setStyle(TableStyle([
        ("FONTSIZE",  (0,0), (-1,-1), 8),
        ("FONTNAME",  (0,0), (-1,-1), "Helvetica"),
        ("PADDING",   (0,0), (-1,-1), 4),
    ]))
    story.append(firma_table)

    # ── Pie de página ────────────────────────────────────────────
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Generado por PAQUETELLEGUE  |  Documento para uso aduanal",
        ParagraphStyle("foot", fontSize=6, fontName="Helvetica",
                       textColor=colors.grey, alignment=TA_CENTER)
    ))

    doc.build(story)
    return ruta_pdf
