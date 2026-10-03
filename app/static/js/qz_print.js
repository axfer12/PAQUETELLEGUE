// PAQUETELLEGUE — Impresion directa via QZ Tray
let _qzListo = false;

async function qzInit() {
  if (_qzListo) return true;
  try {
    if (!qz.websocket.isActive()) await qz.websocket.connect();
    _qzListo = true;
    return true;
  } catch(e) {
    return false;
  }
}

async function imprimirReciboDirecto(guiaId, metodoPago, confirmacion) {
  const pdfUrl = `/guia/${guiaId}/recibo_pdf?metodo_pago=${metodoPago}&confirmacion=${encodeURIComponent(confirmacion||'')}`;

  // 1. Verificar QZ Tray primero — si no está disponible, abrir PDF directamente
  const ok = await qzInit();
  if (!ok) {
    window.open(pdfUrl, '_blank');
    return;
  }

  // 2. QZ Tray disponible — obtener datos raw del recibo
  const url = `/impresion/recibo_raw/${guiaId}?metodo_pago=${metodoPago}&confirmacion=${encodeURIComponent(confirmacion||'')}`;
  let d;
  try {
    const r = await fetch(url);
    if (!r.ok) { window.open(pdfUrl, '_blank'); return; }
    d = await r.json();
  } catch(e) { window.open(pdfUrl, '_blank'); return; }
  if (!d.ok) { alert('Error al obtener recibo: ' + d.error); return; }

  // 3. Obtener impresora configurada
  // impresora desde localStorage o QZ
  let impresora = localStorage.getItem('pl_impresora') || '';

  if (!impresora) {
    // Intentar obtener de la config del servidor
    try {
      // sin endpoint raw disponible
    } catch(e) {}
    // Si no hay impresora guardada, pedir al usuario
    try {
      const impresoras = await qz.printers.find();
      const termicas   = impresoras.filter(i =>
        /epson|thermal|termica|tm-|rp-|xp-|pos|receipt/i.test(i)
      );
      impresora = termicas[0] || impresoras[0] || '';
      if (impresoras.length > 1) {
        impresora = prompt('Selecciona impresora:\n' + impresoras.join('\n'), termicas[0]||impresoras[0]||'');
      }
      if (impresora) localStorage.setItem('pl_impresora', impresora);
    } catch(e) { impresora = ''; }
  }

  if (!impresora) {
    window.open(`/guia/${guiaId}/recibo_pdf?metodo_pago=${metodoPago}&confirmacion=${encodeURIComponent(confirmacion||'')}`, '_blank');
    return;
  }

  // 4. Construir HTML del ticket 80mm
  const lines = d.lines;
  const qrB64 = d.qr_b64 || '';
  const qrUrl = d.qr_url || '';

  var lineasHtml = lines.map(function(l){
    return '<div class="line">' + l.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</div>';
  }).join('');

  var qrHtml = '';
  if(qrB64){
    qrHtml = '<div style="text-align:center;margin:4px 0">'
           + '<div style="font-size:9px;font-weight:bold;margin-bottom:2px">RASTREA TU ENVIO:</div>'
           + '<img src="data:image/png;base64,' + qrB64 + '" style="width:55mm;height:55mm"/>'
           + '</div>';
  }

  const html = '<html><head><style>'
    + 'body{font-family:"Courier New",monospace;font-size:11px;margin:0;padding:2mm;width:72mm;}'
    + '.line{white-space:pre;}'
    + '</style></head><body>'
    + lineasHtml
    + qrHtml
    + '</body></html>';

  // 5. Imprimir
  try {
    const config = qz.configs.create(impresora, {
      size: { width: 80, units: 'mm' },
      margins: { top: 0, right: 2, bottom: 0, left: 2 },
      colorType: 'blackwhite',
      copies: 1
    });
    await qz.print(config, [{ type:'pixel', format:'html', flavor:'plain', data: html }]);
    return true;
  } catch(e) {
    console.error('QZ print error:', e);
    // Fallback a PDF
    window.open(`/guia/${guiaId}/recibo_pdf?metodo_pago=${metodoPago}&confirmacion=${encodeURIComponent(confirmacion||'')}`, '_blank');
  }
}


// ── Impresión etiqueta guía 6x4 ───────────────────────
async function imprimirEtiquetaGuia(guiaId) {
  // 1. Obtener impresora etiquetas
  let impresora = localStorage.getItem('pl_impresora_etiqueta') || '';

  // 2. Verificar QZ
  const ok = await qzInit();
  if (!ok) {
    // Fallback: abrir PDF en nueva pestaña
    window.open('/guia/' + guiaId + '/pdf_oficial', '_blank');
    return false;
  }

  if (!impresora) {
    try {
      const lista = await qz.printers.find();
      const etiqueteras = lista.filter(i => /zebra|rollo|munbyn|label|etiq|dymo|brother ql/i.test(i));
      impresora = etiqueteras[0] || lista[0] || '';
      if (lista.length > 1) {
        impresora = prompt('Selecciona impresora de etiquetas:\n' + lista.join('\n'), etiqueteras[0]||lista[0]||'');
      }
      if (impresora) localStorage.setItem('pl_impresora_etiqueta', impresora);
    } catch(e) {}
  }

  if (!impresora) {
    window.open('/guia/' + guiaId + '/pdf_oficial', '_blank');
    return false;
  }

  // 3. Obtener PDF en base64
  try {
    const r = await fetch('/impresion/guia_pdf_b64/' + guiaId);
    const d = await r.json();
    if (!d.ok) throw new Error(d.error);

    // 4. Imprimir en 4x6 vertical (formato estándar guías Skydropx)
    const config = qz.configs.create(impresora, {
      size:        { width: 4, height: 6, units: 'in' },
      margins:     { top: 0, right: 0, bottom: 0, left: 0 },
      orientation: 'portrait',
      colorType:   'blackwhite',
      scaleContent: true,
      copies: 1
    });

    await qz.print(config, [{
      type:   'pixel',
      format: 'pdf',
      flavor: 'base64',
      data:   d.b64
    }]);
    return true;
  } catch(e) {
    console.error('Error imprimiendo etiqueta:', e);
    window.open('/guia/' + guiaId + '/pdf_oficial', '_blank');
    return false;
  }
}


// ── Impresión invoice carta ───────────────────────────
async function imprimirInvoice(guiaId) {
  const ok = await qzInit();
  if (!ok) {
    window.open('/impresion/invoice_download/' + guiaId, '_blank');
    return false;
  }

  let impresora = localStorage.getItem('pl_impresora_normal') || '';
  if (!impresora) {
    try {
      const lista = await qz.printers.find();
      impresora = lista[0] || '';
      if (lista.length > 1) {
        impresora = prompt('Selecciona impresora normal:\n' + lista.join('\n'), lista[0]||'');
      }
      if (impresora) localStorage.setItem('pl_impresora_normal', impresora);
    } catch(e) {}
  }

  if (!impresora) {
    window.open('/impresion/invoice_download/' + guiaId, '_blank');
    return false;
  }

  try {
    const r = await fetch('/impresion/invoice_pdf/' + guiaId);
    const d = await r.json();
    if (!d.ok) throw new Error(d.error);

    const config = qz.configs.create(impresora, {
      size:    { width: 8.5, height: 11, units: 'in' },
      margins: { top: 0.5, right: 0.5, bottom: 0.5, left: 0.5 },
      copies:  1
    });

    await qz.print(config, [{
      type:   'pixel',
      format: 'pdf',
      flavor: 'base64',
      data:   d.b64
    }]);
    return true;
  } catch(e) {
    console.error('Error imprimiendo invoice:', e);
    window.open('/impresion/invoice_download/' + guiaId, '_blank');
    return false;
  }
}
