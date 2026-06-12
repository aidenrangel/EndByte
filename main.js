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
        note.innerHTML = 'FORM BACKEND NOT CONFIGURED YET — EMAIL US DIRECTLY AT <a href="mailto:aidenrangel@gmail.com" style="color:var(--amber)">AIDENRANGEL@GMAIL.COM</a>';
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
        note.innerHTML = 'SOMETHING WENT WRONG — PLEASE EMAIL <a href="mailto:aidenrangel@gmail.com" style="color:var(--amber)">AIDENRANGEL@GMAIL.COM</a> INSTEAD.';
      });
    });
  }

  /* ---------- scroll reveals (all pages) ---------- */
  var io=new IntersectionObserver(function(entries){
    entries.forEach(function(e){ if(e.isIntersecting){ e.target.classList.add('in'); io.unobserve(e.target); } });
  },{threshold:0.12});
  document.querySelectorAll('.reveal').forEach(function(el){ io.observe(el); });

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
