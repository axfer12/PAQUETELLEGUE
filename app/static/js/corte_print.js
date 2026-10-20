// PAQUETELLEGUE — Impresión del corte (térmica y carta)

function _corteParams(){
  var p = new URLSearchParams(window.location.search);
  return p.toString() ? '?' + p.toString() : '';
}

// ── Hoja carta PDF — siempre disponible ──────────────────────────
function imprimirCortePDF(){
  window.open('/admin/corte_pdf' + _corteParams(), '_blank');
}

// ── Térmica — requiere QZ Tray instalado ─────────────────────────
async function imprimirCorteTermica(){
  var params = _corteParams();

  // Verificar QZ Tray sin esperar timeouts largos
  var qzOk = false;
  try {
    if(typeof qz !== 'undefined' && qz.websocket.isActive()){
      qzOk = true;
    } else if(typeof qz !== 'undefined'){
      await Promise.race([
        qz.websocket.connect(),
        new Promise(function(_, reject){ setTimeout(function(){ reject(new Error('timeout')); }, 2000); })
      ]);
      qzOk = true;
    }
  } catch(e) {
    qzOk = false;
  }

  if(!qzOk){
    // QZ no disponible — ir directo a PDF sin alert molesto
    window.open('/admin/corte_pdf' + params, '_blank');
    return;
  }

  // Obtener líneas del corte
  var d;
  try {
    var r = await fetch('/admin/corte_raw' + params);
    d = await r.json();
    if(!d.ok) throw new Error(d.error || 'Error');
  } catch(e) {
    alert('Error obteniendo corte: ' + e.message);
    return;
  }

  // Seleccionar impresora térmica
  var impresora = localStorage.getItem('pl_impresora') || '';
  if(!impresora){
    try {
      var lista = await qz.printers.find();
      var termicas = lista.filter(function(i){
        return /epson|thermal|termica|tm-|rp-|xp-|pos|receipt|80mm/i.test(i);
      });
      impresora = termicas[0] || lista[0] || '';
      if(lista.length > 1)
        impresora = prompt('Selecciona impresora:\n' + lista.join('\n'), termicas[0]||lista[0]||'');
      if(impresora) localStorage.setItem('pl_impresora', impresora);
    } catch(e) {
      window.open('/admin/corte_pdf' + params, '_blank');
      return;
    }
  }

  if(!impresora){
    window.open('/admin/corte_pdf' + params, '_blank');
    return;
  }

  // Generar HTML ticket 80mm
  var lines = d.lines;
  var lineasHtml = lines.map(function(l){
    return '<div class="line">' +
      l.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') +
      '</div>';
  }).join('');

  var html = '<html><head><style>'
    + 'body{font-family:"Courier New",monospace;font-size:11px;margin:0;padding:2mm;width:72mm;}'
    + '.line{white-space:pre;}'
    + '</style></head><body>'
    + lineasHtml
    + '</body></html>';

  try {
    var config = qz.configs.create(impresora, {
      size:     { width: 80, units: 'mm' },
      margins:  { top: 0, right: 2, bottom: 0, left: 2 },
      colorType:'blackwhite',
      copies:   1
    });
    await qz.print(config, [{ type:'pixel', format:'html', flavor:'plain', data: html }]);
  } catch(e) {
    console.error('QZ error:', e);
    window.open('/admin/corte_pdf' + params, '_blank');
  }
}
