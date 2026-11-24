'use strict';
const $ = (s) => document.querySelector(s);
const state = { products:[], cart:[], catalogLoaded:false, user:null, category:'', search:'' };
const fa = (n) => Number(n||0).toLocaleString('fa-IR');
const rial = (n) => `${fa(n)} ریال`;
const escapeHtml = (s) => String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let toastTimeout;
function toast(message){ const t=$('#toast');t.textContent=message;t.hidden=false;clearTimeout(toastTimeout);toastTimeout=setTimeout(()=>t.hidden=true,3400); }
async function api(path, options={}) {
  const {body, ...other}=options;
  const headers = {'Content-Type': 'application/json'};
  if (other.method && other.method !== 'GET') {
    headers['X-CSRFToken'] = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || '';
  }
  let response;
  try{response=await fetch(`/api${path}`,{...other,headers,body:body==null?undefined:JSON.stringify(body)});}catch{throw new Error('اتصال به سرور برقرار نشد')}
  const data=await response.json().catch(()=>({}));
  if(!response.ok)throw new Error(data.error||'خطای غیرمنتظره');
  return data;
}
function loadCart(){try{state.cart=JSON.parse(localStorage.getItem('arak_cart')||'[]');if (!Array.isArray(state.cart)) state.cart = [];
  const seen = new Set();
  state.cart = state.cart.filter(i => {
    if (!Number.isSafeInteger(i?.id) || i.id < 1 || !Number.isInteger(i.quantity)
        || i.quantity < 1 || i.quantity > 1000 || seen.has(i.id)) return false;
    seen.add(i.id); return true;
  }).slice(0, 50);}catch{state.cart=[]}}
function saveCart(){try{localStorage.setItem('arak_cart',JSON.stringify(state.cart))}catch{}renderCartCount()}
function renderCartCount(){const count=state.cart.reduce((s,x)=>s+x.quantity,0);$('#cartCount').textContent=fa(count);$('#mobileCartCount').textContent=fa(count);$('#mobileCartCount').hidden=!count}
async function loadProducts(){try{
   const d=await api('/products');state.products=d.products;state.catalogLoaded=true;renderCategories();renderProducts();
 }catch(e){toast(e.message);$('#emptyTitle').textContent='بارگذاری محصولات امکان‌پذیر نیست';$('#emptyText').textContent='ارتباط با سرور را بررسی کنید.';$('#emptyState').hidden=false;$('#productGrid').setAttribute('aria-busy','false');$('#resultCount').textContent='خطا در دریافت محصولات';}}
function renderCategories(){
  const cats=[...new Set(state.products.map(p=>p.category).filter(Boolean))];
  if (!cats.includes(state.category)) state.category = '';
  const root=$('#categories');root.innerHTML='<button type="button" class="chip active" data-cat="">همه محصولات</button>'+
    cats.map(c=>`<button type="button" class="chip" data-cat="${escapeHtml(c)}">${escapeHtml(c)}</button>`).join('');
  root.querySelectorAll('[data-cat]').forEach(btn => {const active=btn.dataset.cat===state.category;btn.classList.toggle('active',active);btn.setAttribute('aria-pressed',String(active));});
  root.querySelectorAll('[data-cat]').forEach(btn=>btn.addEventListener('click',()=>{state.category=btn.dataset.cat;root.querySelectorAll('.chip').forEach(n=>{n.classList.toggle('active',n===btn);n.setAttribute('aria-pressed',String(n===btn));});renderProducts();}));
}
function picture(p,cl=''){return p.images?.length?`<img class="${cl}" src="${escapeHtml(p.images[0])}" alt="${escapeHtml(p.name)}" loading="lazy" decoding="async">`:'<span class="product-placeholder" aria-hidden="true">AK</span>'}
function bindImageFallback(root){root.querySelectorAll('img').forEach(img=>{const fallback=()=>{const p=document.createElement('span');p.className='product-placeholder';p.setAttribute('aria-hidden','true');p.textContent='AK';img.replaceWith(p)};img.addEventListener('error',fallback,{once:true});if(img.complete&&!img.naturalWidth)fallback();});}
function renderProducts(){
 const q=state.search.trim().toLocaleLowerCase('fa');
 const ps=state.products.filter(p=>(!state.category||state.category===p.category)&&(!q||p.name.toLocaleLowerCase('fa').includes(q)||p.description.toLocaleLowerCase('fa').includes(q)));
 $('#productGrid').innerHTML=ps.map(p=>`<article class="product-card"><div class="product-photo"><button class="product-open" type="button" aria-label="نمایش ${escapeHtml(p.name)}" data-product="${p.id}">${picture(p)}<span class="stock-tag ${p.stock?'':'unavailable'}">${p.stock?'موجود':'ناموجود'}</span><span class="product-arrow"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M19 5 5 19M5 7v12h12"/></svg></span></button></div><div class="product-meta"><div class="product-category">${escapeHtml(p.category||'محصولات')}</div><div class="product-name">${escapeHtml(p.name)}</div><div class="product-price">${rial(p.price)}</div></div></article>`).join('');
 $('#productGrid').setAttribute('aria-busy','false');$('#resultCount').textContent=`${fa(ps.length)} محصول`;bindImageFallback($('#productGrid'));
 $('#emptyTitle').textContent=state.products.length?'محصولی با این مشخصات پیدا نشد':'هنوز محصولی ثبت نشده';
 $('#emptyText').textContent=state.products.length?'جست‌وجو یا دسته‌بندی را تغییر دهید.':'پس از اضافه‌شدن محصولات، اینجا نمایش داده می‌شوند.';
 $('#emptyState').hidden=ps.length>0;
 $('#productGrid').querySelectorAll('[data-product]').forEach(btn=>btn.addEventListener('click',()=>viewProduct(Number(btn.dataset.product))));
}
let returnFocus=null;
function openOverlay(type){if($('#overlay').hidden)returnFocus=document.activeElement;$('#overlay').hidden=false;const node=type==='drawer'?$('#drawer'):$('#modal');$('#drawer').hidden=type!=='drawer';$('#modal').hidden=type!=='modal';node.hidden=false;document.body.style.overflow='hidden';node.querySelector('[data-close]')?.focus({preventScroll:true});}
function closeOverlay(){const wasOpen=!$('#overlay').hidden;$('#overlay').hidden=true;$('#drawer').hidden=true;$('#modal').hidden=true;document.body.style.overflow='';if(wasOpen&&returnFocus?.isConnected)returnFocus.focus({preventScroll:true});returnFocus=null;}
function cartTotal(){return state.cart.reduce((s,i)=>{const p=state.products.find(p=>p.id===i.id);return s+(p?p.price*i.quantity:0)},0)}
function renderCart(){
  const node=$('#cartItems');
  if (!state.catalogLoaded) {
    node.textContent = 'برای مشاهده سبد، ابتدا محصولات باید بارگذاری شوند.';
    $('#checkoutBtn').disabled = true;
    return;
  }
  const filtered=state.cart.filter(i=>state.products.some(p=>p.id===i.id));
  if(filtered.length!==state.cart.length){state.cart=filtered;saveCart()}
  node.innerHTML=state.cart.length?state.cart.map(i=>{const p=state.products.find(p=>p.id===i.id);return `<div class="cart-item"><div class="cart-thumb" style="display:grid;place-items:center">${picture(p)}</div><div><h4>${escapeHtml(p.name)}</h4><p>${rial(p.price)}</p><div class="qty-control"><button data-qty="${p.id}" data-delta="1">+</button><span>${fa(i.quantity)}</span><button data-qty="${p.id}" data-delta="-1">−</button></div></div></div>`}).join(''):'<div class="cart-empty">سبد خریدت فعلاً خالیه ♡</div>';
  $('#cartTotal').textContent=rial(cartTotal());$('#checkoutBtn').disabled=!state.cart.length;
  bindImageFallback(node);node.querySelectorAll('[data-qty]').forEach(b=>{b.setAttribute('aria-label',Number(b.dataset.delta)>0?'افزایش تعداد':'کاهش تعداد');b.addEventListener('click',()=>changeQty(Number(b.dataset.qty),Number(b.dataset.delta)));});
}
function changeQty(id,delta){let item=state.cart.find(x=>x.id===id);if(!item)return;const p=state.products.find(x=>x.id===id);item.quantity=Math.min(p.stock,1000,item.quantity+delta);if(item.quantity<1)state.cart=state.cart.filter(x=>x.id!==id);saveCart();renderCart()}
function addToCart(id){const p=state.products.find(x=>x.id===id);if(!p||p.stock<1)return toast('این محصول فعلاً موجود نیست');const item=state.cart.find(x=>x.id===id);if(item){if(item.quantity>=Math.min(1000,p.stock))return toast('موجودی بیشتری ثبت نشده');item.quantity++}else { if (state.cart.length >= 50) return toast('حداکثر ۵۰ نوع کالا در هر سفارش'); state.cart.push({id,quantity:1}); }saveCart();closeOverlay();toast('محصول به سبد خرید اضافه شد')}
function viewProduct(id){const p=state.products.find(x=>x.id===id);if(!p)return;
 const images=Array.isArray(p.images)?p.images:[];
 const thumbs=images.length>1?'<div class="gallery-thumbs" aria-label="تصاویر کالا">'+images.map((src,i)=>`<button type="button" class="gallery-thumb" data-image-index="${i}" aria-label="تصویر ${fa(i+1)}" aria-pressed="${i===0}"><img src="${escapeHtml(src)}" alt="" loading="lazy"></button>`).join('')+'</div>':'';
 $('#modalContent').innerHTML=`<div class="gallery-main" id="galleryMain">${picture(p)}</div>${thumbs}<span class="label-sup">${escapeHtml(p.category||'محصولات')}</span><h2 id="modalTitle">${escapeHtml(p.name)}</h2><p>${escapeHtml(p.description||'')}</p><div class="totals"><b>${rial(p.price)}</b><span>${p.stock?`${fa(p.stock)} عدد موجود`:'ناموجود'}</span></div><button id="addProductBtn" class="btn btn-dark full" ${!p.stock?'disabled':''}>افزودن به سبد خرید +</button>`;
 $('#modalContent').querySelectorAll('[data-image-index]').forEach(b=>b.addEventListener('click',()=>{const index=Number(b.dataset.imageIndex);$('#galleryMain').innerHTML=picture({...p,images:[images[index]]});bindImageFallback($('#galleryMain'));$('#modalContent').querySelectorAll('[data-image-index]').forEach(t=>t.setAttribute('aria-pressed',String(t===b)));}));
 bindImageFallback($('#modalContent'));$('#addProductBtn').addEventListener('click',()=>addToCart(id));openOverlay('modal')}
function formField(label,name,type='text',extra=''){return `<div class="field"><label for="f_${name}">${label}</label><input id="f_${name}" name="${name}" type="${type}" ${extra} required></div>`}
function authModal(mode = 'login') {
  const register = mode === 'register';
  const identity = register
    ? formField('نام و نام خانوادگی', 'name') + formField('شماره موبایل', 'phone', 'tel', 'maxlength="11" autocomplete="tel"')
    : formField('موبایل یا نام کاربری', 'username', 'text', 'autocomplete="username"');
  $('#modalContent').innerHTML = `<h2 id="modalTitle">${register ? 'ایجاد حساب کاربری' : 'ورود به حساب'}</h2>
    <form id="authForm">${identity}${formField(register ? 'رمز عبور (حداقل ۱۲ نویسه)' : 'رمز عبور',
      'password', 'password', register ? 'minlength="12" autocomplete="new-password"' : 'autocomplete="current-password"')}
    <button class="btn btn-dark full" type="submit">${register ? 'ثبت‌نام' : 'ورود'}</button></form>
    <p class="form-help"><button class="text-button" id="switchAuth">${register ? 'ورود به حساب موجود' : 'ایجاد حساب جدید'}</button></p>`;
  $('#switchAuth').onclick = () => authModal(register ? 'login' : 'register');
  $('#authForm').onsubmit = async event => {
    event.preventDefault();
    const button = event.submitter;
    button.disabled = true;
    try {
      const body = Object.fromEntries(new FormData(event.currentTarget));
      const result = await api(register ? '/auth/register' : '/auth/login', {method: 'POST', body});
      state.user = result.user;
      closeOverlay();
      toast(register ? 'حساب کاربری ایجاد شد' : 'خوش اومدی ' + state.user.full_name);
    } catch (error) {
      toast(error.message);
    } finally {
      button.disabled = false;
    }
  };
  openOverlay('modal');
}

function accountModal() {
  if (!state.user) return authModal();
  $('#modalContent').innerHTML = `<h2 id="modalTitle">${escapeHtml(state.user.full_name)}</h2>
    <p>${escapeHtml(state.user.phone)}</p><button class="btn btn-dark full" id="accountOrders">سفارش‌های من</button>
    <button class="text-button" id="logout">خروج از حساب</button>`;
  $('#accountOrders').onclick = ordersModal;
  $('#logout').onclick = async () => {
    try {
      await api('/auth/logout', {method: 'POST'});
      state.user = null;
      closeOverlay();
      toast('از حساب خارج شدی');
    } catch (error) {
      toast(error.message);
    }
  };
  openOverlay('modal');
}

async function ordersModal(){if(!state.user)return authModal();try{const d=await api('/orders');$('#modalContent').innerHTML=`<span class="label-sup">YOUR ORDERS</span><h2 id="modalTitle">سفارش‌های من</h2>${d.orders.length?d.orders.map(o=>`<div class="order-row"><strong>سفارش #${fa(o.id)} · ${rial(o.total)}</strong><span>وضعیت: ${escapeHtml(o.status_label)} · ${new Date(o.created_at*1000).toLocaleDateString('fa-IR')}</span><span>کد رهگیری <bdi>${escapeHtml(o.code)}</bdi></span></div>`).join(''):'<p>هنوز سفارشی ثبت نکردی.</p>'}`;openOverlay('modal')}catch(e){toast(e.message)}}
function checkoutModal(){if(!state.cart.length)return;if(!state.user)return authModal();closeOverlay();$('#modalContent').innerHTML=`<span class="label-sup">CHECKOUT</span><h2 id="modalTitle">ثبت سفارش آزمایشی</h2><p>این نسخه هنوز پرداخت آنلاین و ارسال واقعی ندارد. سفارش صرفاً در سیستم ثبت می‌شود.</p><form id="checkoutForm">${formField('نام گیرنده','full_name','text','minlength="2"')}${formField('موبایل','phone','tel','minlength="8"')}<div class="field"><label for="address">نشانی کامل</label><textarea id="address" name="address" required minlength="8"></textarea></div><div class="totals"><span>مبلغ سفارش</span><b>${rial(cartTotal())}</b></div><button class="btn btn-dark full" type="submit">ثبت سفارش بدون پرداخت ↖</button></form>`;
 $('#f_full_name').value = state.user.full_name;
 $('#f_phone').value = state.user.phone;
 let previousPayload = '';
 let token;
 const attemptKey = 'arak_order_attempt';
 $('#checkoutForm').onsubmit = async event => {
   event.preventDefault();
   const button = event.submitter;
   button.disabled = true;
   const form = Object.fromEntries(new FormData(event.currentTarget));
   const items = state.cart.map(i => ({product_id: i.id, quantity: i.quantity}));
   const currentPayload = JSON.stringify({...form, items});
   try {
     // Keep only a hash, not the delivery address or phone, in session storage.
     const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify([state.user.phone, currentPayload])));
     const fingerprint = Array.from(new Uint8Array(digest), n => n.toString(16).padStart(2,'0')).join('');
     let attempt;
     try { attempt = JSON.parse(sessionStorage.getItem(attemptKey) || 'null'); } catch {}
     if (currentPayload !== previousPayload || !token) {
       token = attempt?.fingerprint === fingerprint && /^[0-9a-f-]{36}$/i.test(attempt.token) ? attempt.token : crypto.randomUUID();
       previousPayload = currentPayload;
       try { sessionStorage.setItem(attemptKey, JSON.stringify({fingerprint, token})); } catch {}
     }
     const result = await api('/orders', {method: 'POST', body: {...form, items, token}});
     try { sessionStorage.removeItem(attemptKey); } catch {}
     const purchased = new Map(items.map(i => [i.product_id, i.quantity]));
     state.cart = state.cart.map(i => ({...i, quantity: i.quantity - (purchased.get(i.id) || 0)})).filter(i => i.quantity > 0);
     saveCart();
     await loadProducts();
     closeOverlay();
     toast(`سفارش آزمایشی شماره ${fa(result.order_id)} ثبت شد`);
   } catch (error) {
     toast(error.message);
   } finally {
     button.disabled = false;
   }
 };
 openOverlay('modal');
}

async function init() {
  loadCart();
  renderCartCount();
  await Promise.all([loadProducts(), api('/me').then(user => { state.user = user; }).catch(() => {})]);
}
$('#searchInput').addEventListener('input',e=>{state.search=e.target.value;renderProducts()});
['cartBtn','mobileCartBtn'].forEach(id=>$('#'+id).addEventListener('click',()=>{renderCart();openOverlay('drawer')}));
['accountBtn','mobileAccountBtn'].forEach(id=>$('#'+id).addEventListener('click',accountModal));
['ordersBtn','mobileOrdersBtn'].forEach(id=>$('#'+id).addEventListener('click',ordersModal));
$('#checkoutBtn').addEventListener('click',checkoutModal);
$('#overlay').addEventListener('click',closeOverlay);
document.querySelectorAll('[data-close]').forEach(x=>x.addEventListener('click',closeOverlay));
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeOverlay();return}if(e.key!=='Tab'||$('#overlay').hidden)return;const active=$('#modal').hidden?$('#drawer'):$('#modal');const focusable=[...active.querySelectorAll('button:not([disabled]),a[href],input:not([disabled]),textarea:not([disabled]),select:not([disabled])')].filter(el=>el.getClientRects().length);if(!focusable.length)return;const first=focusable[0],last=focusable.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}});
init();
