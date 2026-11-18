// Floating chat bubble: drag the launcher anywhere, open the chat right next to it.
const GAP = 12, MARGIN = 8, PREFERRED_HEIGHT = 560, MIN_HEIGHT = 260, DRAG_THRESHOLD = 5;

export function clampLauncher({x,y},size,viewport) {
  return {x:Math.min(Math.max(MARGIN,x),viewport.width - size - MARGIN),y:Math.min(Math.max(MARGIN,y),viewport.height - size - MARGIN)};
}
// Place the panel above the launcher when it fits, otherwise below; keep it inside the viewport.
export function panelPlacement(launcher,viewport,width) {
  const panelWidth = Math.min(width,viewport.width - MARGIN * 2);
  const above = launcher.top - GAP - MARGIN;
  const below = viewport.height - launcher.bottom - GAP - MARGIN;
  const placeAbove = above >= Math.min(PREFERRED_HEIGHT,MIN_HEIGHT) && (above >= below || above >= PREFERRED_HEIGHT);
  const height = Math.max(Math.min(PREFERRED_HEIGHT,placeAbove ? above : below),Math.min(MIN_HEIGHT,viewport.height - MARGIN * 2));
  const centered = launcher.left + (launcher.right - launcher.left) / 2 - panelWidth / 2;
  const alignLeft = launcher.left + panelWidth <= viewport.width - MARGIN ? launcher.left : centered;
  const left = Math.min(Math.max(MARGIN,alignLeft),viewport.width - panelWidth - MARGIN);
  const top = placeAbove ? Math.max(MARGIN,launcher.top - GAP - height) : Math.min(launcher.bottom + GAP,viewport.height - height - MARGIN);
  return {left,top,width:panelWidth,height,side:placeAbove ? 'above' : 'below'};
}

const STORE = 'moyeo-chat-bubble';
const viewport = () => ({width:document.documentElement.clientWidth,height:window.innerHeight});
export function initChatBubble({launcher,panel,onToggle}) {
  const size = () => launcher.offsetWidth || 58;
  let position = null;
  try { position = JSON.parse(localStorage.getItem(STORE)); } catch {}
  const apply = () => {
    if (position) {
      position = clampLauncher(position,size(),viewport());
      Object.assign(launcher.style,{left:position.x + 'px',top:position.y + 'px',right:'auto',bottom:'auto'});
    }
    if (panel.hidden) return;
    const place = panelPlacement(launcher.getBoundingClientRect(),viewport(),380);
    Object.assign(panel.style,{left:place.left + 'px',top:place.top + 'px',width:place.width + 'px',height:place.height + 'px',right:'auto',bottom:'auto'});
    panel.dataset.side = place.side;
  };
  let drag = null;
  launcher.addEventListener('pointerdown',event => {
    if (event.button !== 0) return;
    const rect = launcher.getBoundingClientRect();
    drag = {id:event.pointerId,startX:event.clientX,startY:event.clientY,dx:event.clientX - rect.left,dy:event.clientY - rect.top,moved:false};
  });
  window.addEventListener('pointermove',event => {
    if (!drag || event.pointerId !== drag.id) return;
    if (!drag.moved && Math.hypot(event.clientX - drag.startX,event.clientY - drag.startY) < DRAG_THRESHOLD) return;
    if (!drag.moved) { drag.moved = true; launcher.classList.add('dragging'); }
    event.preventDefault();
    position = {x:event.clientX - drag.dx,y:event.clientY - drag.dy};
    apply();
  });
  const end = event => {
    if (!drag || event.pointerId !== drag.id) return;
    const moved = drag.moved;
    drag = null;
    launcher.classList.remove('dragging');
    if (moved) {
      try { localStorage.setItem(STORE,JSON.stringify(position)); } catch {}
      launcher.dataset.justDragged = '1';
      setTimeout(() => { delete launcher.dataset.justDragged; },50);
    }
  };
  window.addEventListener('pointerup',end);
  window.addEventListener('pointercancel',end);
  launcher.addEventListener('keydown',event => {
    const step = event.shiftKey ? 40 : 10;
    const delta = {ArrowLeft:[-step,0],ArrowRight:[step,0],ArrowUp:[0,-step],ArrowDown:[0,step]}[event.key];
    if (!delta || !event.altKey) return;
    event.preventDefault();
    const rect = launcher.getBoundingClientRect();
    position = {x:rect.left + delta[0],y:rect.top + delta[1]};
    apply();
    try { localStorage.setItem(STORE,JSON.stringify(position)); } catch {}
  });
  window.addEventListener('resize',apply);
  apply();
  return {update:apply,wasDragged:() => launcher.dataset.justDragged === '1'};
}
