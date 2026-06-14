(function(){
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- mobile menu (all pages) ---------- */
  var nav = document.querySelector('nav');
  var menuBtn = document.getElementById('menuBtn');
  if(nav && menuBtn){
    function setMenu(open){
      nav.classList.toggle('open', open);
      menuBtn.setAttribute('aria-expanded', open);
      menuBtn.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    }
    menuBtn.addEventListener('click', function(){
      setMenu(!nav.classList.contains('open'));
    });
    // close when a menu link is tapped (so same-page anchors feel right)
    nav.querySelectorAll('.mobilemenu a').forEach(function(a){
      a.addEventListener('click', function(){ setMenu(false); });
    });
    // close on Escape
    document.addEventListener('keydown', function(e){
      if(e.key === 'Escape' && nav.classList.contains('open')){
        setMenu(false);
        menuBtn.focus();
      }
    });
    // close if resized up to desktop
    window.addEventListener('resize', function(){
      if(window.innerWidth > 920 && nav.classList.contains('open')) setMenu(false);
    });

    // collapsible Services group in the mobile menu
    var svcToggle = document.getElementById('mmServicesToggle');
    var svcList = document.getElementById('mmServicesList');
    if(svcToggle && svcList){
      var svcGroup = svcToggle.closest('.mm-group');
      svcToggle.addEventListener('click', function(){
        var open = svcGroup.classList.toggle('open');
        svcToggle.setAttribute('aria-expanded', open);
        svcList.style.maxHeight = open ? svcList.scrollHeight + 'px' : '0';
      });
    }
  }

  /* ---------- hex rain (full-page background, home page only) ---------- */
  var hexCanvas = document.getElementById('hexrain');
  if(hexCanvas && !reduced){
    // ===== TUNABLE: overall visibility of the rain. 0 = invisible, 1 = bold. =====
    var RAIN_INTENSITY = 0.5;   // try 0.3 (whisper) to 0.8 (prominent)
    // =============================================================================

    var ctx = hexCanvas.getContext('2d');
    var cols, drops, speeds, fontSize = 14, dpr = Math.min(window.devicePixelRatio || 1, 2);
    var hexChars = '0123456789ABCDEF';
    var zeroBandTop = 0, zeroBandBot = 0;
    var running = true, rafId = null, frameCount = 0;

    function sizeCanvas(){
      var w = window.innerWidth, h = window.innerHeight;
      hexCanvas.width = w * dpr;
      hexCanvas.height = h * dpr;
      hexCanvas.style.width = w + 'px';
      hexCanvas.style.height = h + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      cols = Math.floor(w / (fontSize * 1.6));
      drops = []; speeds = [];
      for(var i = 0; i < cols; i++){
        drops[i] = Math.random() * (h / fontSize);
        speeds[i] = 0.35 + Math.random() * 0.5; // varied speeds so columns never sync up
      }
      zeroBandTop = h * 0.30;
      zeroBandBot = h * 0.58;
    }
    sizeCanvas();

    function pair(){ return hexChars[Math.floor(Math.random()*16)] + hexChars[Math.floor(Math.random()*16)]; }

    function draw(){
      if(!running){ return; }
      var w = window.innerWidth, h = window.innerHeight;
      // soft trail: translucent bg over the previous frame gives the comet-tail streaks.
      // slightly stronger than a pure trail so faint streaks can't accumulate forever.
      ctx.fillStyle = 'rgba(14,17,22,0.16)';
      ctx.fillRect(0, 0, w, h);
      // every ~90 frames, one extra faint sweep clears any lingering vertical buildup
      // (imperceptible to the eye, but stops static columns from forming over time)
      frameCount++;
      if(frameCount % 90 === 0){
        ctx.fillStyle = 'rgba(14,17,22,0.30)';
        ctx.fillRect(0, 0, w, h);
      }
      ctx.font = fontSize + "px 'IBM Plex Mono', monospace";

      var nearTop = window.scrollY < h * 0.6;

      for(var i = 0; i < cols; i++){
        var x = i * fontSize * 1.6 + 4;
        var y = drops[i] * fontSize;
        var inZeroBand = nearTop && (y > zeroBandTop && y < zeroBandBot);
        var text, alpha;
        if(inZeroBand){
          text = '00';
          var amber = Math.random() < 0.06;
          alpha = (0.10 + Math.random()*0.10) * RAIN_INTENSITY;
          ctx.fillStyle = amber
            ? 'rgba(255,176,32,' + (alpha*1.6).toFixed(3) + ')'
            : 'rgba(120,210,160,' + alpha.toFixed(3) + ')';
        } else {
          text = pair();
          alpha = (0.05 + Math.random()*0.07) * RAIN_INTENSITY;
          ctx.fillStyle = 'rgba(139,149,165,' + alpha.toFixed(3) + ')';
        }
        ctx.fillText(text, x, y);

        // reset a column to the top once it passes the bottom (randomized so they
        // never line up), and give it a fresh random speed each time
        if(y > h && Math.random() > 0.975){
          drops[i] = 0;
          speeds[i] = 0.35 + Math.random() * 0.5;
        }
        drops[i] += speeds[i];
      }
      rafId = requestAnimationFrame(draw);
    }

    function startRain(){ if(!running){ running = true; draw(); } }
    function stopRain(){ running = false; if(rafId) cancelAnimationFrame(rafId); }

    draw();

    document.addEventListener('visibilitychange', function(){
      document.hidden ? stopRain() : startRain();
    });

    var rt;
    window.addEventListener('resize', function(){
      clearTimeout(rt);
      rt = setTimeout(function(){ sizeCanvas(); }, 200);
    });
  }

  /* ---------- instant estimate calculator (home page only) ---------- */
  var estRoot = document.getElementById('estimate');
  if(estRoot){
    // pricing grid: price[service][type][capacityTier]
    // SSD ignores capacity tier (uses 's'); HDD uses s/m/l
    var PRICES = {
      wipe:    { ssd: {s:12, m:12, l:12}, hdd: {s:12, m:16, l:20} },
      destroy: { ssd: {s:15, m:15, l:15}, hdd: {s:15, m:19, l:23} }
    };
    var RESALE_DISCOUNT = 0.5;   // 50% off, wipe only, under the free threshold
    var FREE_THRESHOLD = 50;     // at/above this many drives, resale = FREE (free program)

    var state = { service:'wipe', type:'ssd', cap:'s', qty:1, resale:false };

    var capField = document.getElementById('estCapField');
    var resaleField = document.getElementById('estResaleField');
    var resaleBox = document.getElementById('estResale');
    var qtyInput = document.getElementById('estQty');
    var totalEl = document.getElementById('estTotal');
    var breakEl = document.getElementById('estBreak');
    var ctaEl = document.getElementById('estCta');

    function qualifiesFree(){
      return state.service === 'wipe' && state.resale && state.qty >= FREE_THRESHOLD;
    }

    function perDrive(){
      var base = PRICES[state.service][state.type][state.type === 'ssd' ? 's' : state.cap];
      if(state.service === 'wipe' && state.resale){
        if(state.qty >= FREE_THRESHOLD) return 0;          // free program territory
        base = base * (1 - RESALE_DISCOUNT);               // otherwise 50% off
      }
      return base;
    }

    function fmt(n){ return '$' + (Number.isInteger(n) ? n : n.toFixed(2)); }

    function render(){
      // SSD: capacity irrelevant -> dim it; HDD: active
      if(state.type === 'ssd'){ capField.classList.add('dim'); } else { capField.classList.remove('dim'); }
      // resale only applies to wipe -> dim + uncheck on destroy
      if(state.service === 'destroy'){
        resaleField.classList.add('dim');
        if(state.resale){ state.resale = false; resaleBox.checked = false; }
      } else {
        resaleField.classList.remove('dim');
      }

      // dynamic resale toggle label: 50% off normally, FREE at/above the threshold
      var resaleText = document.getElementById('estResaleText');
      if(resaleText){
        if(state.resale && state.qty >= FREE_THRESHOLD){
          resaleText.innerHTML = 'Let EndByte keep &amp; resell the wiped drives <b class="est-free">— FREE at ' + FREE_THRESHOLD + '+ drives</b>';
        } else {
          resaleText.innerHTML = 'Let EndByte keep &amp; resell the wiped drives <b>— 50% off</b> <span class="est-hint">(free at ' + FREE_THRESHOLD + '+)</span>';
        }
      }

      var free = qualifiesFree();
      var unit = perDrive();
      var total = unit * state.qty;

      var typeLabel = state.type.toUpperCase();
      var capLabel = '';
      if(state.type === 'hdd'){ capLabel = ({s:' ≤4TB', m:' 4–12TB', l:' >12TB'})[state.cap]; }
      var svcLabel = state.service === 'wipe' ? 'wipe' : 'destroy';

      if(free){
        totalEl.textContent = 'FREE';
        totalEl.classList.add('est-isfree');
        breakEl.textContent = state.qty + ' ' + typeLabel + capLabel + ' · qualifies for the free certified destruction program';
        ctaEl.textContent = 'CLAIM FREE DESTRUCTION →';
        var summaryF = state.qty + ' ' + typeLabel + capLabel + ' drive' + (state.qty>1?'s':'') +
                       ', ' + svcLabel + ' — qualifies for FREE certified destruction (resale, ' + FREE_THRESHOLD + '+ drives)';
        ctaEl.setAttribute('data-summary', summaryF);
      } else {
        totalEl.textContent = fmt(total);
        totalEl.classList.remove('est-isfree');
        var resaleLabel = (state.service === 'wipe' && state.resale) ? ' · resale 50% off' : '';
        breakEl.textContent = state.qty + ' ' + typeLabel + capLabel + ' · ' + svcLabel + ' · ' + fmt(unit) + '/drive' + resaleLabel;
        ctaEl.textContent = 'GET THIS QUOTE CONFIRMED →';
        var summary = state.qty + ' ' + typeLabel + capLabel + ' drive' + (state.qty>1?'s':'') +
                      ', ' + svcLabel + resaleLabel + ' — estimated ' + fmt(total);
        ctaEl.setAttribute('data-summary', summary);
      }
    }

    // segmented buttons
    estRoot.querySelectorAll('.est-seg').forEach(function(seg){
      var group = seg.getAttribute('data-group');
      seg.querySelectorAll('.est-opt').forEach(function(btn){
        btn.addEventListener('click', function(){
          seg.querySelectorAll('.est-opt').forEach(function(b){ b.classList.remove('on'); });
          btn.classList.add('on');
          state[group] = btn.getAttribute('data-val');
          render();
        });
      });
    });

    // quantity steppers
    function setQty(v){
      v = Math.max(1, Math.min(9999, v || 1));
      state.qty = v; qtyInput.value = v; render();
    }
    document.getElementById('estMinus').addEventListener('click', function(){ setQty(state.qty - 1); });
    document.getElementById('estPlus').addEventListener('click', function(){ setQty(state.qty + 1); });
    qtyInput.addEventListener('input', function(){ setQty(parseInt(qtyInput.value, 10)); });

    // resale toggle
    resaleBox.addEventListener('change', function(){ state.resale = resaleBox.checked; render(); });

    // CTA: carry the estimate into the contact form, then guide the user to finish it
    ctaEl.addEventListener('click', function(e){
      var summary = ctaEl.getAttribute('data-summary') || '';
      var form = document.getElementById('quoteForm');
      var msg = form ? form.querySelector('[name="message"]') : null;
      var svc = form ? form.querySelector('[name="service"]') : null;
      var nameField = form ? form.querySelector('[name="name"]') : null;

      if(msg){
        msg.value = 'INSTANT ESTIMATE REQUEST\n' +
                    '------------------------\n' +
                    summary + '\n\n' +
                    'Please confirm this quote. Anything else I should know about the drives, I\'ll add here:';
      }
      if(svc){
        svc.value = state.service === 'destroy' ? 'Physical Destruction' : 'Secure Drive Wiping';
      }

      // brief highlight so it's obvious the estimate landed in the form
      if(form){
        form.classList.add('qform-flash');
        setTimeout(function(){ form.classList.remove('qform-flash'); }, 1600);
        // focus the first thing they still need to fill in (name)
        setTimeout(function(){ if(nameField) nameField.focus({preventScroll:true}); }, 650);
      }
      // the href="#contact" handles the smooth scroll
    });

    render();
  }

  /* ---------- cert date (home page only) ---------- */
  var certDate = document.getElementById('certDate');
  if(certDate){
    certDate.textContent = new Date().toISOString().slice(0,10);
  }

  /* ---------- wipe bench (home page only) ---------- */
  var slotsEl = document.getElementById('slots');
  if(slotsEl){
    var SLOTS = 24, slots = [];
    var countEl = document.getElementById('wipeCount');
    var wiped = 0;

    function serial(){
      var c='ABCDEFGHJKMNPQRSTVWXYZ0123456789', s='';
      for(var i=0;i<4;i++) s+=c[Math.floor(Math.random()*c.length)];
      return s;
    }
    for(var i=0;i<SLOTS;i++){
      var el=document.createElement('div');
      el.className='slot';
      el.innerHTML='<div class="sid"><span>S'+String(i+1).padStart(2,'0')+'</span><span class="lamp"></span></div>'+
                   '<div class="bar"><i></i></div><div class="st">EMPTY</div>';
      slotsEl.appendChild(el);
      slots.push({el:el, bar:el.querySelector('.bar i'), st:el.querySelector('.st'),
                  state:'empty', prog:0, pass:1, speed:0, sn:serial()});
    }

    function start(s){
      s.state='wiping'; s.prog=0; s.pass=1;
      s.speed = 0.8 + Math.random()*1.8;
      s.sn = serial();
      s.el.dataset.state='wiping';
      s.st.textContent='PASS 1/3 · '+s.sn;
    }

    function tick(){
      slots.forEach(function(s){
        if(s.state==='wiping'){
          s.prog += s.speed;
          if(s.prog>=100){
            if(s.pass<3){ s.pass++; s.prog=0; s.st.textContent='PASS '+s.pass+'/3 · '+s.sn; }
            else { s.state='verifying'; s.prog=0; s.el.dataset.state='verifying'; s.st.textContent='VERIFYING…'; s.speed*=2.2; }
          }
        } else if(s.state==='verifying'){
          s.prog += s.speed;
          if(s.prog>=100){
            s.state='done'; s.prog=100; s.el.dataset.state='done';
            s.st.textContent='CERTIFIED ✓';
            wiped++; if(countEl) countEl.textContent=wiped;
            setTimeout(function(){ if(s.state==='done'){ s.state='empty'; s.el.dataset.state=''; s.bar.style.width='0%'; s.st.textContent='EMPTY'; } }, 5000+Math.random()*7000);
          }
        } else if(s.state==='empty'){
          if(Math.random()<0.025) start(s);
        }
        if(s.state==='wiping'||s.state==='verifying') s.bar.style.width=Math.min(s.prog,100)+'%';
      });
    }

    slots.forEach(function(s){
      var r=Math.random();
      if(r<0.45){ start(s); s.prog=Math.random()*90; s.pass=1+Math.floor(Math.random()*3); s.st.textContent='PASS '+s.pass+'/3 · '+s.sn; }
      else if(r<0.6){ s.state='done'; s.el.dataset.state='done'; s.st.textContent='CERTIFIED ✓'; s.bar.style.width='100%';
        setTimeout(function(){ s.state='empty'; s.el.dataset.state=''; s.bar.style.width='0%'; s.st.textContent='EMPTY'; }, 4000+Math.random()*8000); }
    });

    if(!reduced){ setInterval(tick, 380); }
    else { slots.forEach(function(s){ if(s.state==='wiping') s.bar.style.width=s.prog+'%'; }); }
  }

  /* ---------- zero word flicker (home page only) ---------- */
  var zw = document.getElementById('zeroWord');
  if(zw && !reduced){
    var glyphs='01x0█0', orig='zero';
    setInterval(function(){
      if(Math.random()<0.18){
        var i=Math.floor(Math.random()*orig.length);
        var g=glyphs[Math.floor(Math.random()*glyphs.length)];
        zw.textContent=orig.slice(0,i)+g+orig.slice(i+1);
        setTimeout(function(){ zw.textContent=orig; }, 140);
      }
    }, 900);
  }

  /* ---------- quote form (home page only) ---------- */
  var qform = document.getElementById('quoteForm');
  if(qform){
    var note = document.getElementById('qfNote');
    qform.addEventListener('submit', function(e){
      e.preventDefault();

      // basic required-field check
      var name = qform.querySelector('[name="name"]');
      var email = qform.querySelector('[name="email"]');
      var msg = qform.querySelector('[name="message"]');
      if(!name.value.trim() || !email.value.trim() || !msg.value.trim() || email.value.indexOf('@') < 0){
        note.className = 'qf-note err';
        note.textContent = 'PLEASE FILL IN NAME, A VALID EMAIL, AND A MESSAGE.';
        return;
      }

      // not configured yet? fail gracefully with a mailto fallback
      if(qform.action.indexOf('YOUR_FORM_ID') !== -1){
        note.className = 'qf-note err';
        note.innerHTML = 'FORM BACKEND NOT CONFIGURED YET — EMAIL US DIRECTLY AT <a href="mailto:info@endbyte.net" style="color:var(--amber)">INFO@ENDBYTE.NET</a>';
        return;
      }

      var btn = qform.querySelector('.qf-submit');
      btn.disabled = true;
      btn.textContent = 'SENDING…';
      note.className = 'qf-note';
      note.textContent = '';

      fetch(qform.action, {
        method: 'POST',
        body: new FormData(qform),
        headers: {'Accept': 'application/json'}
      }).then(function(res){
        if(res.ok){
          qform.classList.add('sent');
          var done = document.createElement('div');
          done.className = 'qf-sent-msg';
          done.innerHTML = '<div class="big">REQUEST RECEIVED ✓</div><p>Thanks — we\'ll get back to you shortly, usually same day. If it\'s urgent, call <a href="tel:+14084206991" style="color:var(--amber)">+1 (408) 420-6991</a>.</p>';
          qform.appendChild(done);
        } else {
          throw new Error('bad status');
        }
      }).catch(function(){
        btn.disabled = false;
        btn.textContent = 'SEND REQUEST';
        note.className = 'qf-note err';
        note.innerHTML = 'SOMETHING WENT WRONG — PLEASE EMAIL <a href="mailto:info@endbyte.net" style="color:var(--amber)">INFO@ENDBYTE.NET</a> INSTEAD.';
      });
    });
  }

  /* ---------- faq accordion (home page only) ---------- */
  var faqItems = document.querySelectorAll('.faq-item');
  if(faqItems.length){
    faqItems.forEach(function(item){
      var q = item.querySelector('.faq-q');
      var a = item.querySelector('.faq-a');
      q.addEventListener('click', function(){
        var open = item.classList.toggle('open');
        q.setAttribute('aria-expanded', open);
        a.style.maxHeight = open ? a.scrollHeight + 'px' : '0';
      });
    });
    window.addEventListener('resize', function(){
      faqItems.forEach(function(item){
        if(item.classList.contains('open')){
          var a = item.querySelector('.faq-a');
          a.style.maxHeight = a.scrollHeight + 'px';
        }
      });
    });
  }

  /* ---------- scroll reveals (all pages) ---------- */
  function revealAll(){
    document.querySelectorAll('.reveal').forEach(function(el){ el.classList.add('in'); });
  }
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(entries){
      entries.forEach(function(e){ if(e.isIntersecting){ e.target.classList.add('in'); io.unobserve(e.target); } });
    },{threshold:0.12});
    document.querySelectorAll('.reveal').forEach(function(el){ io.observe(el); });
    // failsafe: if anything goes wrong, ensure everything is visible after 3s
    setTimeout(revealAll, 3000);
  } else {
    // no observer support — just show everything
    revealAll();
  }

  /* ---------- stat counters (home page only) ---------- */
  var counters = document.querySelectorAll('[data-count]');
  if(counters.length){
    var io2=new IntersectionObserver(function(entries){
      entries.forEach(function(e){
        if(!e.isIntersecting) return;
        io2.unobserve(e.target);
        var el=e.target, target=+el.dataset.count;
        if(reduced){ el.textContent=target.toLocaleString(); return; }
        var t0=null;
        function frame(t){
          if(!t0) t0=t;
          var p=Math.min((t-t0)/1400,1);
          p=1-Math.pow(1-p,3);
          el.textContent=Math.round(target*p).toLocaleString();
          if(p<1) requestAnimationFrame(frame);
        }
        requestAnimationFrame(frame);
      });
    },{threshold:0.5});
    counters.forEach(function(el){ io2.observe(el); });
  }
})();
