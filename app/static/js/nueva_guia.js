// PAQUETELLEGUE WEB - nueva_guia.js
let _rateSeleccionado=null,_descuento=0,_promoId=null,_guiaId=null,_clienteId=null,_quotationIdActual=null;
let _promos=[]; // lista de promos acumuladas [{codigo,descuento,promo_id,nombre}]
let _precioBaseGuia=0, _insumosCarrito=[], _insumosData=[];
const _cpCache={};

async function autoCP(p){
  const cp=document.getElementById(p+'_cp').value.trim();
  if(cp.length!==5){_resetColonias(p);return;}
  if(_cpCache[cp]){_llenarCP(p,_cpCache[cp]);return;}
  // Mostrar cargando
  _setColoniaWidget(p,'loading');
  try{
    const pais=(document.getElementById(p+'_pais')?.value||'MX').toUpperCase();
    const r=await fetch('/api/buscar-cp/'+cp+'?pais='+pais);
    const d=await r.json();
    if(d&&(d.colonias||d.colonia)){_cpCache[cp]=d;_llenarCP(p,d);}
    else{_modoManual(p);}
  }catch(e){_modoManual(p);}
}

function _setColoniaWidget(p, mode, colonias=[]){
  const wrapper=document.getElementById(p+'_colonia_wrapper');
  if(!wrapper)return;

  if(mode==='loading'){
    wrapper.innerHTML='<select id="'+p+'_colonia" class="form-input"><option value="">Buscando...</option></select>';

  } else if(mode==='select'){
    // Crear con DOM para evitar problemas de comillas
    wrapper.innerHTML='';
    const div=document.createElement('div');
    div.style.cssText='display:flex;gap:6px;align-items:center';
    const sel=document.createElement('select');
    sel.id=p+'_colonia'; sel.className='form-input'; sel.style.flex='1';
    colonias.forEach((c,i)=>{
      const opt=document.createElement('option');
      opt.value=c; opt.textContent=c;
      if(i===0)opt.selected=true;
      sel.appendChild(opt);
    });
    const btn=document.createElement('button');
    btn.type='button'; btn.textContent='✏️'; btn.title='Escribir colonia manualmente';
    btn.style.cssText='flex-shrink:0;padding:6px 10px;background:#1a1200;border:1px solid #f0a500;color:#f0a500;border-radius:6px;cursor:pointer;font-size:13px';
    btn.onclick=function(){ _cambiarAManual(p); };
    div.appendChild(sel); div.appendChild(btn);
    wrapper.appendChild(div);

  } else if(mode==='manual'){
    wrapper.innerHTML='';
    const div=document.createElement('div');
    div.style.cssText='display:flex;gap:6px;align-items:center';
    const inp=document.createElement('input');
    inp.id=p+'_colonia'; inp.className='form-input';
    inp.placeholder='Escribe colonia manualmente';
    inp.style.cssText='flex:1;border:1px solid #f0a500;background:#1a1200';
    const btn=document.createElement('button');
    btn.type='button'; btn.textContent='☰'; btn.title='Volver al selector';
    btn.style.cssText='flex-shrink:0;padding:6px 10px;background:#1a1200;border:1px solid #555;color:#aaa;border-radius:6px;cursor:pointer;font-size:13px';
    btn.onclick=function(){ _cambiarASelectDesdeManual(p); };
    const note=document.createElement('small');
    note.style.cssText='color:#f0a500;font-size:11px;display:block;margin-top:3px';
    note.textContent='✏️ Escribe la colonia exacta';
    div.appendChild(inp); div.appendChild(btn);
    wrapper.appendChild(div); wrapper.appendChild(note);

  } else {
    wrapper.innerHTML='<select id="'+p+'_colonia" class="form-input"><option value="">-- Ingresa CP --</option></select>';
  }
}

function _modoManual(p){
  _setColoniaWidget(p,'manual');
  const ciudad=document.getElementById(p+'_ciudad');
  const estado=document.getElementById(p+'_estado');
  if(ciudad){ciudad.value='';ciudad.removeAttribute('readonly');ciudad.style.background='';ciudad.placeholder='Ciudad';}
  if(estado){estado.value='';estado.removeAttribute('readonly');estado.style.background='';estado.placeholder='Estado';}
}

// Cambiar dropdown → input manual (conservando ciudad/estado)
function _cambiarAManual(p){
  const wrapper=document.getElementById(p+'_colonia_wrapper');
  if(!wrapper)return;
  wrapper.innerHTML='';
  const div=document.createElement('div');
  div.style.cssText='display:flex;gap:6px;align-items:center';
  const inp=document.createElement('input');
  inp.id=p+'_colonia'; inp.className='form-input';
  inp.placeholder='Escribe colonia manualmente';
  inp.style.cssText='flex:1;border:1px solid #f0a500;background:#1a1200';
  const btn=document.createElement('button');
  btn.type='button'; btn.textContent='☰'; btn.title='Volver al selector';
  btn.style.cssText='flex-shrink:0;padding:6px 10px;background:#1a1200;border:1px solid #555;color:#aaa;border-radius:6px;cursor:pointer;font-size:13px';
  btn.onclick=function(){ _cambiarASelectDesdeManual(p); };
  const note=document.createElement('small');
  note.style.cssText='color:#f0a500;font-size:11px;display:block;margin-top:3px';
  note.textContent='✏️ Escribe la colonia exacta';
  div.appendChild(inp); div.appendChild(btn);
  wrapper.appendChild(div); wrapper.appendChild(note);
  inp.focus();
}

// Volver de manual → dropdown (recargando colonias del CP)
function _cambiarASelectDesdeManual(p){
  const cp=document.getElementById(p+'_cp');
  if(!cp||!cp.value){_setColoniaWidget(p,'idle');return;}
  const cached=_cpCache[cp.value];
  if(cached){
    const colonias=cached.colonias||(cached.colonia?[cached.colonia]:[]);
    if(colonias.length>0){_setColoniaWidget(p,'select',colonias);}
    else{_setColoniaWidget(p,'manual');}
  } else {
    _buscarCP(p,cp.value);
  }
}

function _resetColonias(p){
  _setColoniaWidget(p,'reset');
  const ciudad=document.getElementById(p+'_ciudad');
  const estado=document.getElementById(p+'_estado');
  if(ciudad){ciudad.value='';ciudad.setAttribute('readonly','');ciudad.style.background='#1a1a0a';}
  if(estado){estado.value='';estado.setAttribute('readonly','');estado.style.background='#1a1a0a';}
}

function _llenarCP(p,d){
  if(d.ciudad)document.getElementById(p+'_ciudad').value=d.ciudad;
  if(d.estado)document.getElementById(p+'_estado').value=d.estado;
  // Restaurar readonly en ciudad/estado si estaban en modo manual
  const ciudad=document.getElementById(p+'_ciudad');
  const estado=document.getElementById(p+'_estado');
  if(ciudad){ciudad.setAttribute('readonly','');ciudad.style.background='#1a1a0a';}
  if(estado){estado.setAttribute('readonly','');estado.style.background='#1a1a0a';}
  const colonias=d.colonias||(d.colonia?[d.colonia]:[]);
  if(colonias.length===0){_setColoniaWidget(p,'manual');return;}
  _setColoniaWidget(p,'select',colonias);
}

let _cTimer=null;
async function buscarCliente(q){
  clearTimeout(_cTimer);
  const lista=document.getElementById('resultados-cliente');
  if(q.length<2){lista.classList.add('hidden');return;}
  _cTimer=setTimeout(async()=>{
    const r=await fetch('/api/clientes/buscar?q='+encodeURIComponent(q));
    const cs=await r.json();
    lista.innerHTML='';
    if(!cs.length){lista.classList.add('hidden');return;}
    cs.forEach(c=>{const div=document.createElement('div');div.className='autocomplete-item';div.textContent=c.nombre+' - '+(c.ciudad||'');div.onclick=()=>seleccionarCliente(c.id);lista.appendChild(div);});
    lista.classList.remove('hidden');
  },300);
}
async function seleccionarCliente(id){
  const r=await fetch('/api/clientes/'+id);const c=await r.json();_clienteId=c.id;
  ['nombre','telefono','calle','colonia','ciudad','estado','cp'].forEach(k=>{const el=document.getElementById('d_'+k);if(el&&c[k])el.value=c[k];});
  if(c.pais)document.getElementById('d_pais').value=c.pais||'MX';
  if(c.email)document.getElementById('d_email').value=c.email||'';
  document.getElementById('resultados-cliente').classList.add('hidden');
  document.getElementById('buscar-cliente').value=c.nombre;
  toggleInternacional();
}
document.addEventListener('click',e=>{if(!e.target.closest('.search-cliente-bar'))document.getElementById('resultados-cliente').classList.add('hidden');});

function toggleInternacional(){
  const pais=(document.getElementById('d_pais').value||'MX').trim().toUpperCase();
  const esInt = pais!=='MX';
  document.getElementById('seccion-internacional').classList.toggle('hidden',!esInt);
  toggleFactura();
  // Cambiar moneda automáticamente según el país
  if(typeof _sugerirMonedaSegunPais === 'function') _sugerirMonedaSegunPais();
  // Cargar tipo de cambio si es internacional
  if(esInt && typeof _cargarTipoCambio === 'function') _cargarTipoCambio();
}

function toggleFactura(){
  // La sección de artículos siempre es visible para internacionales
  // Solo afecta si hay sección-factura con clase hidden (legado)
  const secFact = document.getElementById('seccion-factura');
  if(secFact) secFact.classList.remove('hidden');
}

// Escuchar cambios en proposito del envio
document.querySelectorAll('input[name=shipment_purpose]').forEach(r=>r.addEventListener('change',toggleFactura));

// ── Artículos del envío internacional ────────────────
let _numProductos = 1;

function _crearFilaProducto(idx){
  const div = document.createElement('div');
  div.className = 'producto-row';
  div.dataset.idx = idx;
  div.style.cssText = 'background:#111;border:1px solid #2a2a1a;border-radius:8px;padding:12px;margin-bottom:8px;position:relative';
  div.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <span style="font-size:11px;color:var(--accent);font-weight:600;text-transform:uppercase">Artículo ${idx+1}</span>
      <button type="button" onclick="_eliminarProducto(this)" class="btn btn-secondary btn-sm" style="color:#ff9999;padding:2px 10px;font-size:11px">✖ Eliminar</button>
    </div>
    <div class="form-grid">
      <div class="form-group span-2">
        <label style="font-size:11px">Descripción en inglés *</label>
        <input class="form-input prod-desc" placeholder="e.g. Cotton T-Shirt, Phone case" oninput="_actualizarTotalesProductos()"/>
      </div>
      <div class="form-group">
        <label style="font-size:11px">Cantidad *</label>
        <input class="form-input prod-qty" type="number" value="1" min="1" oninput="_actualizarTotalesProductos()"/>
      </div>
      <div class="form-group">
        <label style="font-size:11px">Valor unitario USD *</label>
        <input class="form-input prod-price" type="number" step="0.01" value="10" min="0" oninput="_actualizarTotalesProductos()"/>
      </div>
      <div class="form-group">
        <label style="font-size:11px">Peso unitario (kg)</label>
        <input class="form-input prod-weight" type="number" step="0.01" value="0.5" min="0.01"/>
      </div>
      <div class="form-group">
        <label style="font-size:11px">HS Code (opcional)</label>
        <input class="form-input prod-hs" placeholder="ej. 6109.10" maxlength="12"/>
      </div>
    </div>`;
  return div;
}

function agregarProducto(){
  const lista = document.getElementById('lista-productos');
  const idx = _numProductos++;
  lista.appendChild(_crearFilaProducto(idx));
  _renumerarProductos();
  _actualizarTotalesProductos();
  // Scroll al nuevo artículo
  lista.lastElementChild.scrollIntoView({behavior:'smooth', block:'nearest'});
}

function _eliminarProducto(btn){
  const row = btn.closest('.producto-row');
  if(document.querySelectorAll('.producto-row').length <= 1){
    alert('Debe haber al menos un artículo'); return;
  }
  row.remove();
  _renumerarProductos();
  _actualizarTotalesProductos();
}

function _renumerarProductos(){
  document.querySelectorAll('.producto-row').forEach((row, i)=>{
    const label = row.querySelector('span[style*="accent"]');
    if(label) label.textContent = `Artículo ${i+1}`;
  });
}

function _actualizarTotalesProductos(){
  const rows = document.querySelectorAll('.producto-row');
  let totalQty = 0, totalValor = 0;
  rows.forEach(row=>{
    const qty = parseInt(row.querySelector('.prod-qty')?.value)||1;
    const price = parseFloat(row.querySelector('.prod-price')?.value)||0;
    totalQty += qty;
    totalValor += qty * price;
  });
  const elQty = document.getElementById('tot-qty');
  const elValor = document.getElementById('tot-valor');
  if(elQty) elQty.textContent = totalQty;
  if(elValor) elValor.textContent = '$' + totalValor.toFixed(2) + ' USD';
  // Sincronizar con el campo de valor declarado si está en USD
  const monedaEl = document.getElementById('moneda_valor');
  const valorEl  = document.getElementById('valor_declarado');
  if(monedaEl && valorEl && monedaEl.value === 'USD' && totalValor > 0){
    valorEl.value = totalValor.toFixed(2);
    if(typeof onMonedaChange === 'function') onMonedaChange();
  }
}

function _getProductos(){
  const rows = document.querySelectorAll('.producto-row');
  return Array.from(rows).map(row=>({
    description_en: row.querySelector('.prod-desc')?.value.trim() || 'General merchandise',
    quantity:       parseInt(row.querySelector('.prod-qty')?.value)  || 1,
    price:          parseFloat(row.querySelector('.prod-price')?.value) || 1,
    weight:         parseFloat(row.querySelector('.prod-weight')?.value) || 0.5,
    hs_code:        row.querySelector('.prod-hs')?.value.trim() || '',
    country_code:   'MX',
  }));
}

// Actualizar totales en tiempo real al cargar
document.addEventListener('DOMContentLoaded', ()=>{
  try {
    // Agregar listeners a la fila inicial de artículos
    document.querySelectorAll('.prod-qty, .prod-price').forEach(el=>{
      el.addEventListener('input', _actualizarTotalesProductos);
    });
    _actualizarTotalesProductos();
  } catch(e) { /* sección internacional no visible aún */ }
});

// ── Seguro ────────────────────────────────────────────
function actualizarSeguro(){
  const chk=document.getElementById('con_seguro');const lbl=document.getElementById('lbl-seguro');
  const val = typeof _getValorDeclaradoMXN === 'function' ? _getValorDeclaradoMXN() : (parseFloat(document.getElementById('valor_declarado').value)||100);
  if(chk.checked){lbl.textContent='Seguro: $'+(val*0.10).toFixed(2)+' MXN';lbl.classList.remove('hidden');}else lbl.classList.add('hidden');
  // Actualizar conversión si está visible
  if(typeof onMonedaChange === 'function') onMonedaChange();
  _actualizarPrecioFinal();
}

// ── Promos acumulables ────────────────────────────────
async function agregarPromo(){
  const input = document.getElementById('codigo_promo');
  const codigo = input.value.trim();
  if(!codigo) return;

  // Verificar que no esté ya aplicado
  if(_promos.find(p => p.codigo === codigo)){
    alert('Este código ya fue agregado.'); return;
  }

  // Precio base actual (sin promos ya aplicadas) — base del rate
  const precioBase = _rateSeleccionado ? _rateSeleccionado.precio_venta : 0;
  // Para descuentos acumulados: precio después de promos anteriores
  const precioConPromos = precioBase - _promos.reduce((s,p)=>s+p.descuento,0);

  const r = await fetch('/api/promocion/validar',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({codigo, precio: precioConPromos,
                          servicio: _rateSeleccionado?.carrier, cliente_id: _clienteId})
  });
  const d = await r.json();

  if(d.ok){
    _promos.push({codigo, descuento: d.descuento, promo_id: d.promo_id, nombre: d.nombre||codigo});
    _recalcularDescuentos();
    input.value = '';
    _renderPromos();
  } else {
    alert('Código inválido: ' + d.error);
  }
}

function _renderPromos(){
  const lista = document.getElementById('lista-promos');
  const totalDiv = document.getElementById('total-descuento');
  if(!lista) return;

  lista.innerHTML = _promos.map((p,i) => `
    <div style="display:flex;justify-content:space-between;align-items:center;background:#0a1a0a;border:1px solid #2a4a2a;border-radius:4px;padding:4px 8px">
      <span style="font-size:12px;color:var(--green)">🏷️ ${p.nombre} — <strong>-$${p.descuento.toFixed(2)}</strong></span>
      <button type="button" onclick="_quitarPromo(${i})" style="background:none;border:none;color:#ff6666;cursor:pointer;font-size:14px;padding:0 4px">✕</button>
    </div>
  `).join('');

  if(_promos.length > 0){
    totalDiv.style.display = 'block';
    totalDiv.textContent = 'Total descuentos: -$' + _descuento.toFixed(2);
  } else {
    totalDiv.style.display = 'none';
  }
}

function _quitarPromo(idx){
  _promos.splice(idx, 1);
  _recalcularDescuentos();
  _renderPromos();
  _actualizarPrecioFinal();
}

function _recalcularDescuentos(){
  // Recalcular cada descuento en cadena (20% sobre precio, luego 10% sobre precio restante)
  const precioBase = _rateSeleccionado ? _rateSeleccionado.precio_venta : 0;
  let precioActual = precioBase;
  let totalDesc = 0;

  // Re-validar todos secuencialmente ya que algunos son % del precio restante
  _promos.forEach(p => {
    totalDesc += p.descuento;
  });

  _descuento = totalDesc;
  _promoId = _promos.length > 0 ? _promos[0].promo_id : null; // mantener compat
  _actualizarPrecioFinal();
}

function _actualizarPrecioFinal(){
  if(!_rateSeleccionado)return;
  const val=parseFloat(document.getElementById('valor_declarado').value)||100;
  const seg=document.getElementById('con_seguro').checked?val*0.10:0;
  _precioBaseGuia = parseFloat((_rateSeleccionado.precio_venta-_descuento+seg).toFixed(2));
  document.getElementById('precio-final-display').textContent='$'+_precioBaseGuia.toFixed(2);
}

// ── Cotizar ───────────────────────────────────────────
async function cotizar(){
  const btn=document.getElementById("btn-cotizar");
  const cont=document.getElementById("rates-container");
  const reqs={r_nombre:"Nombre remitente",r_cp:"CP origen",d_nombre:"Destinatario",d_cp:"CP destino",peso:"Peso",contenido:"Contenido"};
  for(const[id,lbl] of Object.entries(reqs)){const el=document.getElementById(id);if(!el||!el.value.trim()){alert("Falta: "+lbl);return;}}
  btn.disabled=true;btn.textContent="Cotizando...";
  cont.innerHTML="<div class=rates-loading>Consultando...</div>";
  document.getElementById("panel-generar").classList.add("hidden");_rateSeleccionado=null;_quotationIdActual=null;
  const payload={
    peso:parseFloat(document.getElementById("peso")?.value)||1,
    alto:parseFloat(document.getElementById("alto")?.value)||10,
    ancho:parseFloat(document.getElementById("ancho")?.value)||10,
    largo:parseFloat(document.getElementById("largo")?.value)||10,
    cp_origen:document.getElementById("r_cp")?.value.trim()||"",
    cp_destino:document.getElementById("d_cp")?.value.trim()||"",
    pais_origen:document.getElementById("r_pais")?.value.trim()||"MX",
    pais_destino:document.getElementById("d_pais")?.value.trim()||"MX",
    estado_origen:document.getElementById("r_estado")?.value.trim()||"",
    ciudad_origen:document.getElementById("r_ciudad")?.value.trim()||"",
    colonia_origen:document.getElementById("r_colonia")?.value.trim()||"",
    estado_destino:document.getElementById("d_estado")?.value.trim()||"",
    ciudad_destino:document.getElementById("d_ciudad")?.value.trim()||"",
    colonia_destino:document.getElementById("d_colonia")?.value.trim()||"",
    contenido:document.getElementById("contenido")?.value.trim()||"",
    valor_declarado: _getValorDeclaradoMXN()
  };
  try{
    const r=await fetch("/api/cotizar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const d=await r.json();
    if(!d.ok){
      if(d.tipo==='sin_creditos'){
        // Aviso especial de créditos — no es error del operador
        const av=document.getElementById('aviso-creditos');
        if(av){av.classList.remove('hidden');}
        else{
          const div=document.createElement('div');
          div.id='aviso-creditos';
          div.style.cssText='background:#1a2a0a;border:2px solid #C9A84C;border-radius:8px;padding:16px;text-align:center;margin:12px 0';
          div.innerHTML='<div style="font-size:20px;margin-bottom:8px">⚠️</div><div style="font-weight:700;color:#C9A84C;margin-bottom:6px">Saldo insuficiente en el proveedor</div><div style="font-size:13px;color:#9A8A6A;margin-bottom:12px">No hay créditos suficientes para generar esta guía. Recarga saldo y vuelve a intentarlo.</div>';
          const _res=document.getElementById('resultado');if(_res)_res.prepend(div);else document.body.prepend(div);
        }
        btn.disabled=false;btn.textContent='Generar Guia Oficial';
        return;
      }
      throw new Error(d.error);
    }
    _renderRates(d.rates);
    if(d.rates && d.rates.length) _quotationIdActual = d.rates[0].quotation_id;
  }catch(e){cont.innerHTML="<div class=rates-empty style=color:#ff6666>Error: "+e.message+"</div>";}
  finally{btn.disabled=false;btn.textContent="Cotizar Envio";}
}

function _renderRates(rates){
  const cont=document.getElementById("rates-container");
  if(!rates.length){cont.innerHTML="<div class=rates-empty>Sin tarifas disponibles</div>";return;}
  cont.innerHTML="";
  rates.forEach(r=>{
    const div=document.createElement("div");div.className="rate-item";
    div.innerHTML="<div style=display:flex;justify-content:space-between><div><b class=rate-carrier>"+r.carrier+"</b><div class=rate-servicio>"+r.servicio+"</div><div class=rate-dias>"+(r.dias?r.dias+" dias":"")+"</div></div><div style=text-align:right><div class=rate-precio>$"+r.precio_venta.toFixed(2)+"</div><div class=rate-dias>MXN</div></div></div>";
    div.onclick=()=>seleccionarRate(r,div);cont.appendChild(div);
  });
}

function seleccionarRate(rate,el){
  if(rate.success === false){alert("Esta tarifa no está disponible. Selecciona otra.");return;}
  document.querySelectorAll(".rate-item").forEach(i=>i.classList.remove("selected"));el.classList.add("selected");_rateSeleccionado=rate;
  document.getElementById("rate-seleccionado-info").innerHTML="<div class=rate-item style=margin-bottom:10px><b class=rate-carrier>"+rate.carrier+"</b><div class=rate-servicio>"+rate.servicio+"</div></div>";
  _actualizarPrecioFinal();document.getElementById("panel-generar").classList.remove("hidden");
}

// ── Modal de Aranceles EE.UU. ─────────────────────────
function _mostrarModalArancelesUS(onAceptar){
  // Crear modal si no existe
  let m=document.getElementById("modal-aranceles-us");
  if(!m){
    m=document.createElement("div");
    m.id="modal-aranceles-us";
    m.style.cssText="position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.75);padding:16px;";
    m.innerHTML=`
      <div style="background:#1a1a0a;border:2px solid #c9a84c;border-radius:12px;max-width:520px;width:100%;padding:28px 24px;color:#f0e6c8;font-family:inherit;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:18px;">
          <span style="font-size:28px;">🇺🇸⚠️</span>
          <h3 style="margin:0;color:#c9a84c;font-size:18px;line-height:1.3;">Aviso Importante — Aranceles para Envíos a EE.UU.</h3>
        </div>
        <div style="background:#2a200a;border-radius:8px;padding:16px;margin-bottom:18px;font-size:13.5px;line-height:1.7;border-left:3px solid #c9a84c;">
          <p style="margin:0 0 10px;"><strong style="color:#c9a84c;">A partir del 29 de agosto de 2025</strong>, el gobierno de EE.UU. eliminó la exención de aranceles para paquetes menores a $800 USD (<em>de minimis</em>).</p>
          <p style="margin:0 0 10px;"><strong>Todos los envíos a Estados Unidos</strong>, sin importar su valor, están sujetos a:</p>
          <ul style="margin:0 0 10px;padding-left:20px;">
            <li>Aranceles de importación</li>
            <li>Impuestos aduanales</li>
            <li>Despacho aduanal</li>
          </ul>
          <p style="margin:0;color:#ff9966;"><strong>⚠️ El remitente (quien envía desde México) es responsable del pago de estos cargos.</strong> Aplica para todas las paqueterías y servicios internacionales.</p>
        </div>
        <label style="display:flex;align-items:flex-start;gap:10px;cursor:pointer;font-size:13.5px;margin-bottom:20px;">
          <input type="checkbox" id="chk-acepta-aranceles" style="margin-top:3px;width:16px;height:16px;accent-color:#c9a84c;flex-shrink:0;"/>
          <span>He informado al cliente sobre los aranceles aduanales vigentes para envíos a EE.UU. y el cliente acepta que el remitente cubrirá dichos cargos si aplican.</span>
        </label>
        <div style="display:flex;gap:10px;justify-content:flex-end;">
          <button id="btn-aranceles-cancelar" style="background:#333;color:#ccc;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;font-size:14px;">Cancelar</button>
          <button id="btn-aranceles-continuar" style="background:#c9a84c;color:#0a0a00;border:none;padding:10px 24px;border-radius:6px;cursor:pointer;font-size:14px;font-weight:700;opacity:0.5;" disabled>Continuar</button>
        </div>
      </div>`;
    document.body.appendChild(m);
    document.getElementById("chk-acepta-aranceles").addEventListener("change",function(){
      document.getElementById("btn-aranceles-continuar").disabled=!this.checked;
      document.getElementById("btn-aranceles-continuar").style.opacity=this.checked?"1":"0.5";
    });
    document.getElementById("btn-aranceles-cancelar").addEventListener("click",function(){
      m.remove();
      const btn=document.getElementById("btn-generar");
      if(btn){btn.disabled=false;btn.textContent="Generar Guia Oficial";}
    });
  }
  document.getElementById("btn-aranceles-continuar").onclick=function(){
    m.remove();
    onAceptar();
  };
  // Reset checkbox cada vez
  const chk=document.getElementById("chk-acepta-aranceles");
  if(chk){chk.checked=false;document.getElementById("btn-aranceles-continuar").disabled=true;document.getElementById("btn-aranceles-continuar").style.opacity="0.5";}
}

// ── Generar Guia ──────────────────────────────────────
async function generarGuia(){
  if(!_rateSeleccionado){alert("Selecciona un servicio");return;}
  // Validar que el rate sea de la cotización actual
  if(_quotationIdActual && _rateSeleccionado.quotation_id !== _quotationIdActual){
    alert("La cotización ha cambiado. Por favor selecciona un servicio de la lista actualizada.");
    return;
  }
  const btn=document.getElementById("btn-generar");btn.disabled=true;btn.textContent="Generando...";
  const g=id=>document.getElementById(id)?.value.trim()||"";
  const paisDest=(g("d_pais")||"MX").toUpperCase();
  const esInt=paisDest!=="MX";

  // Mostrar aviso obligatorio de aranceles si el destino es EE.UU.
  if(paisDest==="US"){
    _mostrarModalArancelesUS(()=>_ejecutarGenerarGuia(true));
    return;
  }
  _ejecutarGenerarGuia(false);
}

async function _ejecutarGenerarGuia(aceptaArancelesUS){
  const btn=document.getElementById("btn-generar");btn.disabled=true;btn.textContent="Generando...";
  const g=id=>document.getElementById(id)?.value.trim()||"";
  const paisDest=(g("d_pais")||"MX").toUpperCase();
  const esInt=paisDest!=="MX";

  // Validar factura si es necesario
  const purpose=document.querySelector("input[name=shipment_purpose]:checked")?.value||"personal";
  if(esInt&&['commercial','sample'].includes(purpose)){
    const prods=_getProductos();
    const invalido=prods.find(p=>!p.description_en||p.price<=0);
    if(invalido){alert("Completa la descripcion y precio de todos los productos");btn.disabled=false;btn.textContent="Generar Guia Oficial";return;}
  }

  const payload={
    remitente:{nombre:g("r_nombre"),telefono:g("r_telefono"),calle:g("r_calle"),colonia:g("r_colonia"),ciudad:g("r_ciudad"),estado:g("r_estado"),cp:g("r_cp"),pais:g("r_pais")||"MX"},
    destinatario:{nombre:g("d_nombre"),telefono:g("d_telefono"),calle:g("d_calle"),colonia:g("d_colonia"),ciudad:g("d_ciudad"),estado:g("d_estado"),cp:g("d_cp"),pais:paisDest,email:g("d_email")},
    paquete:{
      peso:parseFloat(document.getElementById("peso").value),
      alto:parseFloat(document.getElementById("alto").value)||10,
      ancho:parseFloat(document.getElementById("ancho").value)||10,
      largo:parseFloat(document.getElementById("largo").value)||10,
      contenido:g("contenido"),
      valor_declarado: _getValorDeclaradoMXN(),
      valor_declarado_usd: _getValorDeclaradoUSD(),
      hs_code:"",
      consignment_note_packaging_code:document.getElementById("tipo_empaque")?.value||"4G",
      productos_factura: esInt?_getProductos():[]
    },
    rate:_rateSeleccionado,
    contenido:g("contenido"),
    referencia:g("referencia"),
    valor_declarado: _getValorDeclaradoMXN(),
    valor_declarado_usd: _getValorDeclaradoUSD(),
    con_seguro:document.getElementById("con_seguro").checked,
    descuento:_descuento,
    promo_id:_promoId,
    promos:_promos,
    cliente_id:_clienteId,
    metodo_pago:document.getElementById("metodo-pago")?.value||"efectivo",
    confirmacion_terminal:g("confirmacion")||"",
    customs_payment_payer:document.querySelector("input[name=customs_payer]:checked")?.value||"recipient",
    shipment_purpose:purpose,
    acepta_aranceles_us: aceptaArancelesUS===true
  };

  if(document.getElementById("guardar_cliente").checked){
    const cr=await fetch("/api/clientes",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload.destinatario)});
    const crd=await cr.json();if(crd.ok)payload.cliente_id=crd.id;
  }
  try{
    const r=await fetch("/api/generar_guia",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const d=await r.json();
    if(!d.ok){
      if(d.tipo==='sin_creditos'){
        const av=document.getElementById('aviso-creditos');
        if(av){av.classList.remove('hidden');}
        else{
          const div=document.createElement('div');
          div.id='aviso-creditos';
          div.style.cssText='background:#1a2a0a;border:2px solid #C9A84C;border-radius:8px;padding:16px;text-align:center;margin:12px 0';
          div.innerHTML='<div style="font-size:20px;margin-bottom:8px">⚠️</div><div style="font-weight:700;color:#C9A84C;margin-bottom:6px">Saldo insuficiente en el proveedor</div><div style="font-size:13px;color:#9A8A6A;margin-bottom:12px">No hay créditos suficientes para generar esta guía. Recarga saldo y vuelve a intentarlo.</div>';
          const _res=document.getElementById('resultado');if(_res)_res.prepend(div);else document.body.prepend(div);
        }
        btn.disabled=false;btn.textContent='Generar Guia Oficial';
        return;
      }
      throw new Error(d.error);
    }

    // Si el shipment aún está procesando, hacer polling desde el frontend
    if(d.pending && d.shipment_id){
      const guiaIdBd = d.guia_id;
      const proveedor = d.proveedor || 'sky';
      btn.textContent='⏳ Guía en espera... (0s)';
      btn.style.background='#8B6914';
      let intentos=0; const maxIntentos=120;
      const ctx=d._ctx;
      const poll=setInterval(async()=>{
        intentos++;
        btn.textContent=`⏳ Guía en espera... (${intentos*5}s)`;
        try{
          const ps=await fetch('/api/shipment_status/'+d.shipment_id+'?proveedor='+proveedor);
          const pd=await ps.json();

          if(intentos>=maxIntentos){
            clearInterval(poll);
            // La guía ya está en BD como en_espera — el proveedor la completará via webhook
            alert(`⏳ La guía quedó en espera.\n\nEl proveedor la está procesando. Cuando esté lista aparecerá automáticamente en el Historial.`);
            btn.disabled=false;btn.textContent='Generar Guia Oficial';btn.style.background='';
            // Mostrar resultado parcial con la info disponible
            _mostrarResultadoEspera(d, guiaIdBd, btn);
            return;
          }
          if(!pd.ok){
            clearInterval(poll);
            alert('Error consultando estado: ' + pd.error);
            btn.disabled=false;btn.textContent='Generar Guia Oficial';btn.style.background='';
            return;
          }
          if(!pd.pending){
            clearInterval(poll);
            // Polling completó — actualizar la guía en BD que ya existe
            if(guiaIdBd){
              const cr=await fetch('/api/actualizar_guia_espera/'+guiaIdBd,{method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({numero_guia:pd.tracking||pd.numero_guia, label_url:pd.label_url})});
              const cd=await cr.json();
              const resultado={...pd, guia_id:guiaIdBd, precio_final:d.precio_final};
              _mostrarResultado(resultado, btn);
            } else {
              // Fallback: completar_guia
              const cr=await fetch('/api/completar_guia',{method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({...pd,shipment_id:d.shipment_id,_ctx:ctx})});
              const cd=await cr.json();
              _mostrarResultado(cd, btn);
            }
            btn.style.background='';
          }
        }catch(e){clearInterval(poll);alert('Error: '+e.message);btn.disabled=false;btn.textContent='Generar Guia Oficial';btn.style.background='';}
      },5000);
      return;
    }

    _mostrarResultado(d, btn);
  }catch(e){alert("Error: "+e.message);btn.disabled=false;btn.textContent="Generar Guia Oficial";}
}

async function _mostrarResultado(d, btn){
  _guiaId = d.guia_id || null;
  const precioEnvio = (d.precio_final != null) ? parseFloat(d.precio_final) : 0;

  // Guardar insumos ANTES de mostrar precio final — esperar respuesta
  let totalInsumos = 0;
  if(_guiaId && _insumosCarrito.length > 0){
    totalInsumos = _insumosCarrito.reduce((s,i) => s + i.subtotal, 0);
    await _guardarInsumosGuia(_guiaId);
  }

  const precioFinal = precioEnvio + totalInsumos;
  document.getElementById("resultado-numero").textContent = "N. Guia: " + (d.numero_guia || "—");
  document.getElementById("resultado-precio").textContent = "$" + precioFinal.toFixed(2) + " MXN"
    + (totalInsumos > 0 ? " (envío $" + precioEnvio.toFixed(2) + " + insumos $" + totalInsumos.toFixed(2) + ")" : "");
  if(_guiaId){
    document.getElementById("btn-pdf-oficial").href = "/guia/" + _guiaId + "/pdf_oficial";
  }
  document.getElementById("panel-resultado").classList.remove("hidden");
  document.getElementById("panel-generar").classList.add("hidden");
  if(btn){btn.disabled=false;btn.textContent="Generar Guia Oficial";}
  // Limpiar borrador — guía generada exitosamente
  if(typeof _limpiarBorrador === 'function') _limpiarBorrador();

  // Invoice internacional — mostrar botón destacado y abrir automáticamente
  const paisDest = document.getElementById("d_pais")?.value?.toUpperCase() || "MX";
  const btnInv = document.getElementById("btn-invoice");
  if(paisDest !== "MX" && _guiaId){
    btnInv.style.display = "inline-flex";
    btnInv.style.background = "#2a5f2a";
    btnInv.style.color = "#88ff88";
    btnInv.style.fontWeight = "700";
    btnInv.style.border = "2px solid #88ff88";
    btnInv.textContent = "📄 Imprimir / Descargar Invoice";
    // Abrir invoice automáticamente tras 1.5s
    setTimeout(() => imprimirInvoiceSiAplica(), 1500);
  } else {
    btnInv.style.display = "none";
  }
}

// ── Modal Recibo ──────────────────────────────────────
function abrirModalRecibo(){
  // Mostrar método de pago seleccionado en el modal
  var m = document.getElementById("metodo-pago");
  var display = document.getElementById("modal-metodo-display");
  if(m && display){
    var labels = {"efectivo":"Efectivo","tarjeta_debito":"Tarjeta Débito","tarjeta_credito":"Tarjeta Crédito","transferencia":"Transferencia"};
    display.textContent = labels[m.value] || m.value;
  }
  document.getElementById("modal-recibo").classList.remove("hidden");
}
function cerrarModal(){document.getElementById("modal-recibo").classList.add("hidden");}
function toggleTerminal(){const m=document.getElementById("metodo-pago").value;document.getElementById("conf-terminal").classList.toggle("hidden",!["tarjeta_debito","tarjeta_credito"].includes(m));}
function descargarRecibo(){
  const m=document.getElementById("metodo-pago").value;
  const c=document.getElementById("confirmacion").value.trim();
  if(["tarjeta_debito","tarjeta_credito"].includes(m)&&!c){alert("Ingresa el numero de aprobacion");return;}
  const promosParam = _promos.length > 0 ? "&promos="+encodeURIComponent(JSON.stringify(_promos)) : "";
  window.open("/guia/"+_guiaId+"/recibo_pdf?metodo_pago="+m+"&confirmacion="+encodeURIComponent(c)+promosParam,"_blank");
  cerrarModal();
}

// ── Nueva Guia ────────────────────────────────────────
function nuevaGuia(){
  if(typeof _limpiarBorrador === 'function') _limpiarBorrador();
  _rateSeleccionado=null;_descuento=0;_promoId=null;_guiaId=null;_clienteId=null;_numProductos=1;_promos=[];_renderPromos();
  // Limpiar artículos internacionales — dejar solo el primero en blanco
  const listaProductos = document.getElementById('lista-productos');
  if(listaProductos){
    listaProductos.innerHTML='';
    listaProductos.appendChild(_crearFilaProducto(0));
    document.querySelectorAll('#lista-productos .prod-qty, #lista-productos .prod-price').forEach(el=>el.addEventListener('input',_actualizarTotalesProductos));
    _actualizarTotalesProductos();
  }
  _insumosCarrito=[];_precioBaseGuia=0;_renderCarrito();
  const ip=document.getElementById('insumos-panel');if(ip)ip.style.display='none';
  const bt=document.getElementById('btn-toggle-insumos');if(bt)bt.textContent='+ Agregar';
  ["d_nombre","d_telefono","d_calle","d_colonia","d_ciudad","d_estado","d_cp","d_email","referencia","codigo_promo","buscar-cliente"].forEach(id=>{const el=document.getElementById(id);if(el)el.value="";});
  document.getElementById("d_pais").value="MX";
  document.getElementById("peso").value="1";
  ["alto","ancho","largo"].forEach(id=>document.getElementById(id).value="10");
  document.getElementById("contenido").value="";
  document.getElementById("valor_declarado").value="100";
  document.getElementById("con_seguro").checked=false;
  document.getElementById("guardar_cliente").checked=false;
  document.getElementById("lbl-seguro").classList.add("hidden");
  document.getElementById("lbl-promo").textContent="";
  document.getElementById("rates-container").innerHTML="<div class=rates-empty>Llena los datos y presiona Cotizar</div>";
  document.getElementById("panel-generar").classList.add("hidden");
  document.getElementById("panel-resultado").classList.add("hidden");
  document.getElementById("seccion-internacional").classList.add("hidden");
  if(document.getElementById("seccion-factura")) document.getElementById("seccion-factura").classList.add("hidden");
  // Resetear productos factura
  const lista=document.getElementById("lista-productos");
  if(lista){lista.querySelectorAll('.producto-row:not(:first-child)').forEach(r=>r.remove());}
  const btn=document.getElementById("btn-generar");btn.disabled=false;btn.textContent="Generar Guia Oficial";
}

async function imprimirDirecto(){
  const m=document.getElementById("metodo-pago").value;
  const c=document.getElementById("confirmacion").value.trim();
  if(["tarjeta_debito","tarjeta_credito"].includes(m)&&!c){alert("Ingresa el numero de aprobacion");return;}
  const btn=document.getElementById("btn-imprimir-directo");
  btn.disabled=true;btn.textContent="Imprimiendo...";
  try {
    await imprimirReciboDirecto(_guiaId, m, c);
  } catch(e) {
    alert("Error: "+e.message);
  } finally {
    btn.disabled=false;btn.textContent="🖨️ Imprimir Directo";
    cerrarModal();
  }
}

async function imprimirEtiqueta(){
  if(!_guiaId){alert("Primero genera la guia");return;}
  const btn=document.getElementById("btn-imprimir-etiqueta");
  btn.disabled=true;btn.textContent="Imprimiendo...";
  try {
    await imprimirEtiquetaGuia(_guiaId);
  } catch(e) {
    alert("Error: "+e.message);
  } finally {
    btn.disabled=false;btn.textContent="🖨️ Imprimir Etiqueta";
  }
}

async function imprimirInvoiceSiAplica(){
  if(!_guiaId) return;
  const btn=document.getElementById("btn-invoice");
  btn.disabled=true;
  try { await imprimirInvoice(_guiaId); }
  catch(e){ alert("Error: "+e.message); }
  finally { btn.disabled=false; }
}

// Mostrar botón invoice solo si es envío internacional
function _checkInternacional(){
  const pais=(document.getElementById("d_pais")?.value||"MX").toUpperCase();
  const btn=document.getElementById("btn-invoice");
  if(btn) btn.style.display = pais!=="MX" ? "" : "none";
}
document.getElementById("d_pais")?.addEventListener("change", _checkInternacional);

// Auto-cargar colonias al iniciar si el CP ya está precargado
document.addEventListener('DOMContentLoaded', function(){
  if(document.getElementById('r_cp')?.value?.length === 5) autoCP('r');
  if(document.getElementById('d_cp')?.value?.length === 5) autoCP('d');
});

async function _mostrarResultadoEspera(d, guiaIdBd, btn){
  // Mostrar panel de resultado con estatus "en espera"
  _guiaId = guiaIdBd || d.guia_id || null;
  const precioEnvio = d.precio_final ? parseFloat(d.precio_final) : 0;

  let totalInsumos = 0;
  if(_guiaId && _insumosCarrito.length > 0){
    totalInsumos = _insumosCarrito.reduce((s,i) => s + i.subtotal, 0);
    await _guardarInsumosGuia(_guiaId);
  }

  const precioFinal = precioEnvio + totalInsumos;
  document.getElementById("resultado-numero").textContent = "⏳ EN ESPERA — Proveedor procesando...";
  document.getElementById("resultado-precio").textContent = "$" + precioFinal.toFixed(2) + " MXN"
    + (totalInsumos > 0 ? " (envío $" + precioEnvio.toFixed(2) + " + insumos $" + totalInsumos.toFixed(2) + ")" : "");
  const btnPdf = document.getElementById("btn-pdf-oficial");
  if(btnPdf) btnPdf.style.display = 'none';

  // Botón para reintentar el polling manualmente
  const panelRes = document.getElementById("panel-resultado");
  let btnReintentar = document.getElementById("btn-reintentar-espera");
  if(!btnReintentar){
    btnReintentar = document.createElement("button");
    btnReintentar.id = "btn-reintentar-espera";
    btnReintentar.textContent = "🔄 Verificar si ya está lista";
    btnReintentar.style.cssText = "margin-top:10px;width:100%;padding:10px;background:#1a3a1a;border:1px solid #4CAF50;color:#4CAF50;border-radius:6px;cursor:pointer;font-weight:700;font-size:14px";
    btnReintentar.onclick = function(){ _reintentarEspera(d.shipment_id, guiaIdBd, d._ctx, d.precio_final); };
    panelRes.appendChild(btnReintentar);
  }

  document.getElementById("panel-resultado").classList.remove("hidden");
  document.getElementById("panel-generar").classList.add("hidden");
  if(btn){btn.disabled=false;btn.textContent="Generar Guia Oficial";}
}

// ── Reintentar polling manualmente ────────────────────────────────
async function _reintentarEspera(shipmentId, guiaIdBd, ctx, precioFinal){
  const btnR = document.getElementById("btn-reintentar-espera");
  if(btnR){ btnR.disabled=true; btnR.textContent="🔄 Verificando..."; }
  try{
    const ps = await fetch('/api/shipment_status/' + shipmentId);
    const pd = await ps.json();
    if(!pd.ok){
      alert('Error al verificar: ' + (pd.error||'Sin respuesta'));
      if(btnR){ btnR.disabled=false; btnR.textContent="🔄 Verificar si ya está lista"; }
      return;
    }
    if(pd.pending){
      alert('⏳ El proveedor aún está procesando la guía.\nIntenta de nuevo en 1-2 minutos.');
      if(btnR){ btnR.disabled=false; btnR.textContent="🔄 Verificar si ya está lista"; }
      return;
    }
    // ¡Ya está lista!
    if(btnR) btnR.remove();
    if(guiaIdBd){
      await fetch('/api/actualizar_guia_espera/'+guiaIdBd, {method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({numero_guia:pd.tracking||pd.numero_guia, label_url:pd.label_url})});
      _mostrarResultado({...pd, guia_id:guiaIdBd, precio_final:precioFinal}, null);
    } else {
      const cr = await fetch('/api/completar_guia', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({...pd, shipment_id:shipmentId, _ctx:ctx})});
      const cd = await cr.json();
      _mostrarResultado(cd, null);
    }
  }catch(e){
    alert('Error: ' + e.message);
    if(btnR){ btnR.disabled=false; btnR.textContent="🔄 Verificar si ya está lista"; }
  }
}

// ── INSUMOS ──────────────────────────────────────────────────────────────────

async function _cargarInsumos(){
  if(_insumosData.length > 0) return;
  try{
    const r = await fetch('/api/insumos');
    _insumosData = await r.json();
    const sel = document.getElementById('insumo-select');
    _insumosData.forEach(ins => {
      const opt = document.createElement('option');
      opt.value = ins.id;
      opt.textContent = ins.nombre + ' — $' + parseFloat(ins.precio).toFixed(2);
      opt.dataset.precio = ins.precio;
      opt.dataset.nombre = ins.nombre;
      sel.appendChild(opt);
    });
  }catch(e){ console.error('Error cargando insumos:', e); }
}

function toggleInsumos(){
  const panel = document.getElementById('insumos-panel');
  const btn   = document.getElementById('btn-toggle-insumos');
  if(panel.style.display === 'none'){
    panel.style.display = 'block';
    btn.textContent = '— Ocultar';
    _cargarInsumos();
  } else {
    panel.style.display = 'none';
    btn.textContent = '+ Agregar';
  }
}

function agregarInsumo(){
  const sel = document.getElementById('insumo-select');
  const qty = parseInt(document.getElementById('insumo-qty').value) || 1;
  if(!sel.value) return;
  const precio = parseFloat(sel.options[sel.selectedIndex].dataset.precio);
  const nombre = sel.options[sel.selectedIndex].dataset.nombre;
  const insumo_id = parseInt(sel.value);

  // Si ya está en carrito, sumar cantidad
  const existente = _insumosCarrito.find(i => i.insumo_id === insumo_id);
  if(existente){
    existente.cantidad += qty;
    existente.subtotal = existente.cantidad * existente.precio_unitario;
  } else {
    _insumosCarrito.push({
      insumo_id, nombre,
      cantidad: qty,
      precio_unitario: precio,
      subtotal: qty * precio
    });
  }
  _renderCarrito();
}

function _renderCarrito(){
  const lista = document.getElementById('insumos-lista');
  lista.innerHTML = '';
  let totalInsumos = 0;
  _insumosCarrito.forEach((item, idx) => {
    totalInsumos += item.subtotal;
    const div = document.createElement('div');
    div.style.cssText = 'display:flex;justify-content:space-between;align-items:center;background:var(--surface2);padding:6px 8px;border-radius:4px;font-size:13px';
    div.innerHTML = `
      <span>${item.nombre} ×${item.cantidad}</span>
      <span style="display:flex;gap:8px;align-items:center">
        <strong style="color:var(--gold)">$${item.subtotal.toFixed(2)}</strong>
        <button type="button" onclick="_quitarInsumo(${idx})" style="background:none;border:none;color:#ff9999;cursor:pointer;font-size:14px">✕</button>
      </span>`;
    lista.appendChild(div);
  });

  // Actualizar subtotal y precio total
  const sub = document.getElementById('insumos-subtotal');
  if(_insumosCarrito.length > 0){
    sub.textContent = 'Insumos: $' + totalInsumos.toFixed(2);
    // Actualizar precio mostrado en el panel
    const totalFinal = _precioBaseGuia + totalInsumos;
    const disp = document.getElementById('precio-final-display');
    if(disp) disp.textContent = '$' + totalFinal.toFixed(2);
  } else {
    sub.textContent = '';
    const disp = document.getElementById('precio-final-display');
    if(disp && _precioBaseGuia > 0) disp.textContent = '$' + _precioBaseGuia.toFixed(2);
  }
}

function _quitarInsumo(idx){
  _insumosCarrito.splice(idx, 1);
  _renderCarrito();
}

// Guardar insumos en BD después de generar guía
async function _guardarInsumosGuia(guiaId){
  if(_insumosCarrito.length === 0) return;
  try{
    await fetch('/api/guia/' + guiaId + '/insumos', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(_insumosCarrito)
    });
  }catch(e){ console.error('Error guardando insumos:', e); }
}

// ── Moneda del valor declarado ────────────────────────────────
let _tcMXNUSD = 17.5; // tipo de cambio fallback
let _tcCargado = false;

async function _cargarTipoCambio(){
  if(_tcCargado) return;
  try{
    const r = await fetch('/api/tipo_cambio');
    const d = await r.json();
    if(d.usd_mxn) { _tcMXNUSD = d.usd_mxn; _tcCargado = true; }
  }catch(e){}
}

function onMonedaChange(){
  const moneda = document.getElementById('moneda_valor').value;
  const lbl    = document.getElementById('lbl-valor-declarado');
  const conv   = document.getElementById('lbl-conversion');
  const val    = parseFloat(document.getElementById('valor_declarado').value) || 0;
  if(moneda === 'USD'){
    lbl.textContent = 'Valor declarado (USD)';
    const mxn = val * _tcMXNUSD;
    conv.style.display = 'block';
    conv.textContent = `≈ $${mxn.toFixed(0)} MXN (TC: ${_tcMXNUSD.toFixed(2)})`;
  } else {
    lbl.textContent = 'Valor declarado (MXN)';
    const usd = val / _tcMXNUSD;
    conv.style.display = 'block';
    conv.textContent = `≈ $${usd.toFixed(2)} USD (TC: ${_tcMXNUSD.toFixed(2)})`;
  }
  actualizarSeguro();
}

// Actualizar conversión cuando cambia el valor
document.addEventListener('DOMContentLoaded', () => {
  _cargarTipoCambio();
  const inp = document.getElementById('valor_declarado');
  if(inp) inp.addEventListener('input', () => onMonedaChange());
});

// Al cambiar a envío internacional — sugerir USD
function _sugerirMonedaSegunPais(){
  const pais = document.getElementById('d_pais')?.value?.toUpperCase() || 'MX';
  const sel  = document.getElementById('moneda_valor');
  if(!sel) return;
  if(pais !== 'MX' && sel.value !== 'USD'){
    sel.value = 'USD';
    onMonedaChange();
  } else if(pais === 'MX' && sel.value !== 'MXN'){
    sel.value = 'MXN';
    onMonedaChange();
  }
}

// Obtener valor declarado siempre en MXN para el backend
function _getValorDeclaradoMXN(){
  const val    = parseFloat(document.getElementById('valor_declarado').value) || 100;
  const moneda = document.getElementById('moneda_valor').value;
  return moneda === 'USD' ? val * _tcMXNUSD : val;
}

// Obtener valor declarado en USD para el invoice
function _getValorDeclaradoUSD(){
  const val    = parseFloat(document.getElementById('valor_declarado').value) || 100;
  const moneda = document.getElementById('moneda_valor').value;
  return moneda === 'USD' ? val : val / _tcMXNUSD;
}

// ══════════════════════════════════════════════════════════════════
// AUTOGUARDADO — Guarda el formulario en localStorage cada 15s
// y al cambiar cualquier campo. Al recargar, ofrece restaurar.
// ══════════════════════════════════════════════════════════════════

const _DRAFT_KEY = 'paquetellegue_draft_v1';

// Campos a guardar (ids del formulario)
const _DRAFT_FIELDS = [
  // Destinatario
  'd_nombre','d_telefono','d_calle','d_colonia','d_ciudad',
  'd_estado','d_cp','d_pais','d_email',
  // Paquete
  'peso','alto','ancho','largo','contenido','tipo_empaque',
  'valor_declarado','moneda_valor','con_seguro',
];

function _guardarBorrador(){
  try {
    const data = { ts: Date.now(), campos: {} };
    _DRAFT_FIELDS.forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      data.campos[id] = el.type === 'checkbox' ? el.checked : el.value;
    });
    // Guardar productos internacionales
    data.productos = _getProductos ? _getProductos() : [];
    // Solo guardar si hay algo útil (destinatario con nombre)
    if (data.campos['d_nombre'] || data.campos['d_cp']) {
      localStorage.setItem(_DRAFT_KEY, JSON.stringify(data));
    }
  } catch(e) { console.warn('Autoguardado fallido:', e); }
}

function _restaurarBorrador(data){
  try {
    Object.entries(data.campos || {}).forEach(([id, val]) => {
      const el = document.getElementById(id);
      if (!el) return;
      if (el.type === 'checkbox') {
        el.checked = val;
      } else {
        el.value = val;
      }
    });
    // Disparar eventos para que se actualicen los dropdowns
    const dpais = document.getElementById('d_pais');
    if (dpais) dpais.dispatchEvent(new Event('change'));
    const dcp = document.getElementById('d_cp');
    if (dcp && dcp.value) setTimeout(() => autoCP('d'), 500);
    // Restaurar moneda
    if (typeof onMonedaChange === 'function') onMonedaChange();
    if (typeof actualizarSeguro === 'function') actualizarSeguro();
  } catch(e) { console.warn('Restaurar borrador fallido:', e); }
}

function _limpiarBorrador(){
  try { localStorage.removeItem(_DRAFT_KEY); } catch(e) {}
}

function _verificarBorradorAlCargar(){
  try {
    const raw = localStorage.getItem(_DRAFT_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    if (!data || !data.ts) return;

    // Solo mostrar si tiene datos útiles
    const nombre = data.campos?.d_nombre || '';
    const cp     = data.campos?.d_cp || '';
    if (!nombre && !cp) return;

    // Calcular cuánto tiempo hace (max 24h)
    const mins = Math.floor((Date.now() - data.ts) / 60000);
    if (mins > 1440) { _limpiarBorrador(); return; }
    const tiempoStr = mins < 1 ? 'hace un momento' :
                      mins < 60 ? `hace ${mins} min` :
                      `hace ${Math.floor(mins/60)}h`;

    // Mostrar banner de restauración
    const banner = document.createElement('div');
    banner.id = 'draft-banner';
    banner.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px">
        <div>
          <strong style="color:var(--accent)">📋 Envío pendiente</strong>
          <span style="color:var(--text-sub);font-size:13px;margin-left:8px">
            ${nombre ? `Destinatario: <b style="color:var(--text)">${nombre}</b>` : `CP: <b style="color:var(--text)">${cp}</b>`}
            — ${tiempoStr}
          </span>
        </div>
        <div style="display:flex;gap:8px">
          <button onclick="_onRestaurar()" class="btn btn-primary" style="font-size:13px;padding:6px 16px">
            ✅ Continuar envío
          </button>
          <button onclick="_onDescartarBorrador()" class="btn btn-secondary" style="font-size:13px;padding:6px 12px">
            ✖ Descartar
          </button>
        </div>
      </div>
    `;
    banner.style.cssText = `
      position:fixed;top:0;left:0;right:0;z-index:9999;
      background:#1a1a00;border-bottom:2px solid var(--accent);
      padding:12px 20px;box-shadow:0 4px 20px rgba(0,0,0,.5);
    `;
    document.body.prepend(banner);
    // Mover el contenido hacia abajo
    document.querySelector('.main-content').style.marginTop = '70px';

    // Guardar la data para restaurar
    window._pendingDraft = data;
  } catch(e) { console.warn('Error verificando borrador:', e); }
}

function _onRestaurar(){
  if (window._pendingDraft) {
    _restaurarBorrador(window._pendingDraft);
    window._pendingDraft = null;
  }
  _cerrarBanner();
}

function _onDescartarBorrador(){
  _limpiarBorrador();
  window._pendingDraft = null;
  _cerrarBanner();
}

function _cerrarBanner(){
  const b = document.getElementById('draft-banner');
  if (b) b.remove();
  const mc = document.querySelector('.main-content');
  if (mc) mc.style.marginTop = '';
}

// Inicializar autoguardado al cargar
document.addEventListener('DOMContentLoaded', () => {
  // Verificar si hay borrador guardado
  _verificarBorradorAlCargar();

  // Autoguardar al cambiar cualquier campo
  _DRAFT_FIELDS.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('change', _guardarBorrador);
    if (el.tagName === 'INPUT') el.addEventListener('input', _guardarBorrador);
  });

  // Autoguardar cada 15 segundos
  setInterval(_guardarBorrador, 15000);
});

// Limpiar borrador cuando se genera la guía exitosamente
const _origMostrarResultado = typeof _mostrarResultado !== 'undefined' ? _mostrarResultado : null;
document.addEventListener('guia-generada', () => _limpiarBorrador());
