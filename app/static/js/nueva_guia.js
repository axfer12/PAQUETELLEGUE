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
    note.textContent='✏️ Escribe la colonia exacta como aparece en Skydropx';
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
  note.textContent='✏️ Escribe la colonia exacta como aparece en Skydropx';
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
}

function toggleFactura(){
  const purpose=document.querySelector('input[name=shipment_purpose]:checked')?.value||'personal';
  const esInt=!document.getElementById('seccion-internacional').classList.contains('hidden');
  const necesita=['commercial','sample'].includes(purpose);
  const secFact=document.getElementById('seccion-factura');
  if(secFact) secFact.classList.toggle('hidden',!(esInt&&necesita));
}

// Escuchar cambios en proposito del envio
document.querySelectorAll('input[name=shipment_purpose]').forEach(r=>r.addEventListener('change',toggleFactura));

// ── Factura Comercial ────────────────────────────────
let _numProductos=1;
function agregarProducto(){
  if(_numProductos>=5){alert('Maximo 5 productos');return;}
  const idx=_numProductos++;
  const div=document.createElement('div');
  div.className='producto-row';
  div.dataset.idx=idx;
  div.innerHTML=`<div class="form-grid" style="background:#111;padding:10px;border-radius:6px;margin-bottom:8px;border:1px solid #2a2a1a">
    <div class="form-group span-2">
      <label style="font-size:11px">Descripcion (ingles) *</label>
      <input class="form-input prod-desc" placeholder="e.g. Cotton T-Shirt"/>
    </div>
    <div class="form-group"><label style="font-size:11px">Cantidad *</label><input class="form-input prod-qty" type="number" value="1" min="1"/></div>
    <div class="form-group"><label style="font-size:11px">Valor unitario USD *</label><input class="form-input prod-price" type="number" step="0.01" value="10"/></div>
    <div class="form-group"><label style="font-size:11px">Peso unitario kg</label><input class="form-input prod-weight" type="number" step="0.01" value="0.5"/></div>
    <div class="form-group"><label style="font-size:11px">HS Code</label><input class="form-input prod-hs" placeholder="ej. 6109.10" maxlength="10"/></div>
    <div class="form-group"><label style="font-size:11px">Pais de origen</label><input class="form-input prod-country" value="MX" maxlength="2"/></div>
    <div class="form-group span-2"><button type="button" onclick="this.closest('.producto-row').remove()" class="btn btn-secondary btn-sm" style="width:100%;color:#ff9999">Eliminar producto</button></div>
  </div>`;
  document.getElementById('lista-productos').appendChild(div);
}

function _getProductos(){
  const rows=document.querySelectorAll('.producto-row');
  return Array.from(rows).map(row=>({
    description_en: row.querySelector('.prod-desc')?.value.trim()||'General merchandise',
    quantity:       parseInt(row.querySelector('.prod-qty')?.value)||1,
    price:          parseFloat(row.querySelector('.prod-price')?.value)||1,
    weight:         parseFloat(row.querySelector('.prod-weight')?.value)||0.5,
    hs_code:        row.querySelector('.prod-hs')?.value.trim()||'',
    country_code:   (row.querySelector('.prod-country')?.value.trim()||'MX').toUpperCase(),
  }));
}

// ── Seguro ────────────────────────────────────────────
function actualizarSeguro(){
  const chk=document.getElementById('con_seguro');const lbl=document.getElementById('lbl-seguro');
  const val=parseFloat(document.getElementById('valor_declarado').value)||100;
  if(chk.checked){lbl.textContent='Seguro: $'+(val*0.10).toFixed(2)+' MXN';lbl.classList.remove('hidden');}else lbl.classList.add('hidden');
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
    valor_declarado:parseFloat(document.getElementById("valor_declarado")?.value)||100
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
          div.innerHTML='<div style="font-size:20px;margin-bottom:8px">⚠️</div><div style="font-weight:700;color:#C9A84C;margin-bottom:6px">Saldo insuficiente en Skydropx</div><div style="font-size:13px;color:#9A8A6A;margin-bottom:12px">No hay créditos suficientes para generar esta guía. Recarga saldo y vuelve a intentarlo.</div><a href="https://pro.skydropx.com" target="_blank" style="background:#C9A84C;color:#000;padding:8px 20px;border-radius:4px;font-weight:700;font-size:13px;text-decoration:none">💳 Recargar en Skydropx</a>';
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
      valor_declarado:parseFloat(document.getElementById("valor_declarado").value)||100,
      hs_code:"",
      consignment_note_packaging_code:document.getElementById("tipo_empaque")?.value||"4G",
      productos_factura: esInt?_getProductos():[]
    },
    rate:_rateSeleccionado,
    contenido:g("contenido"),
    referencia:g("referencia"),
    valor_declarado:parseFloat(document.getElementById("valor_declarado").value)||100,
    con_seguro:document.getElementById("con_seguro").checked,
    descuento:_descuento,
    promo_id:_promoId,
    promos:_promos,
    cliente_id:_clienteId,
    metodo_pago:document.getElementById("metodo-pago")?.value||"efectivo",
    confirmacion_terminal:g("confirmacion")||"",
    customs_payment_payer:document.querySelector("input[name=customs_payer]:checked")?.value||"recipient",
    shipment_purpose:purpose
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
          div.innerHTML='<div style="font-size:20px;margin-bottom:8px">⚠️</div><div style="font-weight:700;color:#C9A84C;margin-bottom:6px">Saldo insuficiente en Skydropx</div><div style="font-size:13px;color:#9A8A6A;margin-bottom:12px">No hay créditos suficientes para generar esta guía. Recarga saldo y vuelve a intentarlo.</div><a href="https://pro.skydropx.com" target="_blank" style="background:#C9A84C;color:#000;padding:8px 20px;border-radius:4px;font-weight:700;font-size:13px;text-decoration:none">💳 Recargar en Skydropx</a>';
          const _res=document.getElementById('resultado');if(_res)_res.prepend(div);else document.body.prepend(div);
        }
        btn.disabled=false;btn.textContent='Generar Guia Oficial';
        return;
      }
      throw new Error(d.error);
    }

    // Si el shipment aún está procesando, hacer polling desde el frontend
    if(d.pending && d.shipment_id){
      const guiaIdBd = d.guia_id; // Ya guardada en BD como en_espera
      btn.textContent='⏳ Guía en espera... (0s)';
      btn.style.background='#8B6914';
      let intentos=0; const maxIntentos=120;  // 120 × 5s = 600s máximo
      const ctx=d._ctx;
      const poll=setInterval(async()=>{
        intentos++;
        btn.textContent=`⏳ Guía en espera... (${intentos*5}s)`;
        try{
          const ps=await fetch('/api/shipment_status/'+d.shipment_id);
          const pd=await ps.json();

          if(intentos>=maxIntentos){
            clearInterval(poll);
            // La guía ya está en BD como en_espera — el webhook de Skydropx la completará
            alert('⏳ La guía quedó en espera.\n\nSkydropx la está procesando. Cuando esté lista aparecerá automáticamente en el Historial.\n\nRevisa también en pro.skydropx.com');
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
  _rateSeleccionado=null;_descuento=0;_promoId=null;_guiaId=null;_clienteId=null;_numProductos=1;_promos=[];_renderPromos();
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
  document.getElementById("resultado-numero").textContent = "⏳ EN ESPERA — Skydropx procesando...";
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
      alert('⏳ Skydropx aún está procesando la guía.\nIntenta de nuevo en 1-2 minutos.');
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
