//0
function createBlackBox() {
  if (document.getElementById("black-box")) return;
  injectCondraUiStyles();

  const box = document.createElement("div");

  box.id = "black-box";
  // structure: header (drag) + content + resize handle
  const header = document.createElement('div');
  header.id = 'black-box-header';
  header.style.cursor = 'move';
  header.style.padding = '10px 12px';
  header.style.background = 'linear-gradient(180deg, rgba(255,255,255,0.075), rgba(255,255,255,0.035))';
  header.style.borderBottom = '1px solid rgba(255,255,255,0.10)';
  header.style.fontSize = '12px';
  header.style.color = '#f7f9fc';
  header.style.display = 'flex';
  header.style.alignItems = 'center';
  header.style.justifyContent = 'space-between';
  header.style.minHeight = '42px';

  const brand = document.createElement('div');
  brand.id = 'black-box-brand';
  brand.style.display = 'flex';
  brand.style.alignItems = 'center';
  brand.style.gap = '8px';
  brand.style.minWidth = '0';

  const brandDot = document.createElement('span');
  brandDot.id = 'black-box-brand-dot';
  brandDot.style.width = '8px';
  brandDot.style.height = '8px';
  brandDot.style.borderRadius = '999px';
  brandDot.style.background = '#9ee493';
  brandDot.style.boxShadow = '0 0 0 4px rgba(158,228,147,0.12)';

  const brandText = document.createElement('span');
  brandText.id = 'black-box-brand-text';
  brandText.textContent = 'Condra';
  brandText.style.fontSize = '13px';
  brandText.style.fontWeight = '760';
  brandText.style.letterSpacing = '0';
  brandText.style.whiteSpace = 'nowrap';

  brand.appendChild(brandDot);
  brand.appendChild(brandText);

  const buttonLabel = document.createElement('span');
  buttonLabel.id = 'black-box-button-label';
  buttonLabel.innerText = 'C';
  buttonLabel.style.display = 'none';
  buttonLabel.style.fontSize = '24px';
  buttonLabel.style.lineHeight = '1';
  buttonLabel.style.fontWeight = '700';

  const closeButton = document.createElement('button');
  closeButton.id = 'black-box-close';
  closeButton.type = 'button';
  closeButton.innerText = '×';
  closeButton.style.width = '28px';
  closeButton.style.height = '28px';
  closeButton.style.border = '1px solid rgba(255,255,255,0.14)';
  closeButton.style.borderRadius = '999px';
  closeButton.style.background = 'rgba(255,255,255,0.06)';
  closeButton.style.color = 'rgba(247,249,252,0.86)';
  closeButton.style.cursor = 'pointer';
  closeButton.style.fontSize = '17px';
  closeButton.style.lineHeight = '1';
  closeButton.style.padding = '0';
  closeButton.style.flex = '0 0 auto';

  header.appendChild(brand);
  header.appendChild(buttonLabel);
  header.appendChild(closeButton);

  const content = document.createElement('div');
  content.id = 'black-box-content';
  content.style.padding = '14px 14px 15px';
  content.style.whiteSpace = 'pre-wrap';
  content.style.overflowY = 'auto';
  content.style.fontSize = '14px';
  content.style.lineHeight = '1.5';
  content.innerText = '';

  const resizeHandle = document.createElement('div');
  resizeHandle.id = 'black-box-resize';
  resizeHandle.style.position = 'absolute';
  resizeHandle.style.width = '14px';
  resizeHandle.style.height = '14px';
  resizeHandle.style.left = '6px';
  resizeHandle.style.bottom = '6px';
  resizeHandle.style.cursor = 'sw-resize';
  resizeHandle.style.background = 'transparent';

  const bottomResizeHandle = document.createElement('div');
  bottomResizeHandle.id = 'black-box-bottom-resize';
  bottomResizeHandle.style.position = 'absolute';
  bottomResizeHandle.style.height = '12px';
  bottomResizeHandle.style.left = '48px';
  bottomResizeHandle.style.right = '48px';
  bottomResizeHandle.style.bottom = '0';
  bottomResizeHandle.style.cursor = 's-resize';
  bottomResizeHandle.style.background = 'transparent';

  const rightResizeHandle = document.createElement('div');
  rightResizeHandle.id = 'black-box-right-resize';
  rightResizeHandle.style.position = 'absolute';
  rightResizeHandle.style.width = '14px';
  rightResizeHandle.style.height = '14px';
  rightResizeHandle.style.right = '6px';
  rightResizeHandle.style.bottom = '6px';
  rightResizeHandle.style.cursor = 'se-resize';
  rightResizeHandle.style.background = 'transparent';

  box.appendChild(header);
  box.appendChild(content);
  box.appendChild(resizeHandle);
  box.appendChild(bottomResizeHandle);
  box.appendChild(rightResizeHandle);

  box.style.position = "fixed";
  box.style.width = "360px";
  box.style.height = "300px";
  box.style.left = Math.max(16, window.innerWidth - 360 - 16) + 'px';
  box.style.top = '16px';
  box.style.background = "linear-gradient(180deg, rgba(28,29,32,0.98), rgba(13,14,17,0.98))";
  box.style.color = "#f4f7fb";
  box.style.padding = "10px";
  box.style.border = "1px solid rgba(255,255,255,0.13)";
  box.style.borderRadius = "14px";
  box.style.zIndex = "999999";
  box.style.fontFamily = "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial";
  box.style.whiteSpace = 'pre-wrap';
  box.style.boxSizing = 'border-box';
  box.style.overflow = 'hidden';
  box.style.display = 'flex';
  box.style.flexDirection = 'column';
  box.style.userSelect = 'none';
  box.style.padding = '0';
  box.style.boxShadow = '0 24px 70px rgba(0,0,0,0.30), 0 8px 22px rgba(0,0,0,0.22), inset 0 1px 0 rgba(255,255,255,0.08)';
  box.style.backdropFilter = 'blur(18px) saturate(1.08)';
  box.style.webkitBackdropFilter = 'blur(18px) saturate(1.08)';
  box.style.transformOrigin = 'right top';
  box.style.transition = 'width 180ms ease, height 180ms ease, border-radius 180ms ease';
  box.style.right = '';
  box.style.bottom = '';

  document.body.appendChild(box);

  // Load saved position/size
  loadBoxState();

  function getExpandedBoxWidth() {
    const width = parseInt(box.dataset.expandedWidth || box.style.width || '360', 10);
    return Number.isFinite(width) ? width : 360;
  }

  function placePanelTopRight() {
    const expandedWidth = getExpandedBoxWidth();
    box.style.left = Math.max(16, window.innerWidth - expandedWidth - 16) + 'px';
    box.style.top = '16px';
  }

  function setBoxCollapsed(collapsed) {
    box.dataset.collapsed = collapsed ? '1' : '0';
    if (collapsed) {
      if (box.style.width !== '48px') box.dataset.expandedWidth = box.style.width;
      if (box.style.height !== '48px') box.dataset.expandedHeight = box.style.height;
      const currentLeft = parseFloat(box.style.left || '0');
      const currentWidth = box.offsetWidth || parseInt(box.style.width || box.dataset.expandedWidth || '360', 10) || 360;
      const rightEdge = Number.isFinite(currentLeft) ? currentLeft + currentWidth : window.innerWidth;
      const collapsedLeft = Math.max(0, Math.min(window.innerWidth - 48, rightEdge - 48));
      box.style.left = collapsedLeft + 'px';
      box.style.width = '48px';
      box.style.height = '48px';
      box.style.borderRadius = '999px';
      box.style.cursor = 'pointer';
      header.style.cursor = 'pointer';
      header.style.justifyContent = 'center';
      header.style.height = '100%';
      header.style.minHeight = '0';
      header.style.padding = '0';
      header.style.background = 'transparent';
      header.style.borderBottom = '0';
      brand.style.display = 'none';
      content.style.display = 'none';
      resizeHandle.style.display = 'none';
      bottomResizeHandle.style.display = 'none';
      rightResizeHandle.style.display = 'none';
      closeButton.style.display = 'none';
      buttonLabel.style.display = 'inline-flex';
      buttonLabel.style.alignItems = 'center';
      buttonLabel.style.justifyContent = 'center';
      buttonLabel.style.color = '#101318';
      buttonLabel.style.background = '#9ee493';
      buttonLabel.style.width = '100%';
      buttonLabel.style.height = '100%';
      buttonLabel.style.borderRadius = '999px';
      return;
    }

    placePanelTopRight();
    box.style.width = box.dataset.expandedWidth || '360px';
    box.style.height = box.dataset.expandedHeight || '300px';
    box.style.borderRadius = '14px';
    box.style.cursor = 'default';
    header.style.cursor = 'move';
    header.style.justifyContent = 'space-between';
    header.style.height = '';
    header.style.minHeight = '42px';
    header.style.padding = '10px 12px';
    header.style.background = 'linear-gradient(180deg, rgba(255,255,255,0.075), rgba(255,255,255,0.035))';
    header.style.borderBottom = '1px solid rgba(255,255,255,0.10)';
    brand.style.display = 'flex';
    content.style.display = 'block';
    resizeHandle.style.display = 'block';
    bottomResizeHandle.style.display = 'block';
    rightResizeHandle.style.display = 'block';
    closeButton.style.display = 'inline-block';
    buttonLabel.style.display = 'none';
    updateBlackBoxText();
    saveBoxState();
  }

  setBoxCollapsed(false);

  closeButton.addEventListener('mousedown', (e) => {
    e.stopPropagation();
  });
  closeButton.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    setBoxCollapsed(true);
    saveBoxState();
  });

  // Dragging
  let dragging = false;
  let movedWhileDragging = false;
  let dragOffsetX = 0;
  let dragOffsetY = 0;
  let dragStartX = 0;
  let dragStartY = 0;
  let collapsedPointerDown = false;
  let collapsedPointerId = null;
  let collapsedDragOffsetX = 0;
  let collapsedDragOffsetY = 0;
  let collapsedMoved = false;

  function openCollapsedBox() {
    if (box.dataset.collapsed !== '1') return;
    setBoxCollapsed(false);
  }
  window.condraOpenPanel = openCollapsedBox;

  box.addEventListener('pointerdown', (e) => {
    if (box.dataset.collapsed !== '1') return;
    e.preventDefault();
    e.stopPropagation();
    collapsedPointerDown = true;
    collapsedPointerId = e.pointerId;
    collapsedMoved = false;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    const rect = box.getBoundingClientRect();
    collapsedDragOffsetX = e.clientX - rect.left;
    collapsedDragOffsetY = e.clientY - rect.top;
    box.setPointerCapture(e.pointerId);
  });

  box.addEventListener('pointermove', (e) => {
    if (!collapsedPointerDown || e.pointerId !== collapsedPointerId) return;
    const movedDistance = Math.hypot(e.clientX - dragStartX, e.clientY - dragStartY);
    if (movedDistance < 4) return;
    collapsedMoved = true;
    let x = e.clientX - collapsedDragOffsetX;
    let y = e.clientY - collapsedDragOffsetY;
    x = Math.max(getExpandedBoxWidth() - box.offsetWidth, Math.min(window.innerWidth - box.offsetWidth, x));
    y = Math.max(0, Math.min(window.innerHeight - box.offsetHeight, y));
    box.style.left = x + 'px';
    box.style.top = y + 'px';
  });

  box.addEventListener('pointerup', (e) => {
    if (!collapsedPointerDown || e.pointerId !== collapsedPointerId) return;
    e.preventDefault();
    e.stopPropagation();
    collapsedPointerDown = false;
    collapsedPointerId = null;
    try {
      box.releasePointerCapture(e.pointerId);
    } catch (err) {}
    if (collapsedMoved) {
      saveBoxState();
      return;
    }
    openCollapsedBox();
  });

  box.addEventListener('click', (e) => {
    if (box.dataset.collapsed !== '1') return;
    e.preventDefault();
    e.stopPropagation();
  });

  header.addEventListener('mousedown', (e) => {
    if (box.dataset.collapsed === '1') return;
    dragging = true;
    movedWhileDragging = false;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    const rect = box.getBoundingClientRect();
    dragOffsetX = e.clientX - rect.left;
    dragOffsetY = e.clientY - rect.top;
    document.addEventListener('mousemove', onDrag);
    document.addEventListener('mouseup', stopDrag);
  });
  function onDrag(e) {
    if (!dragging) return;
    const movedDistance = Math.hypot(e.clientX - dragStartX, e.clientY - dragStartY);
    if (movedDistance < 4) return;
    let x = e.clientX - dragOffsetX;
    let y = e.clientY - dragOffsetY;
    x = Math.max(0, Math.min(window.innerWidth - box.offsetWidth, x));
    y = Math.max(0, Math.min(window.innerHeight - box.offsetHeight, y));
    movedWhileDragging = true;
    box.style.left = x + 'px';
    box.style.top = y + 'px';
  }
  function stopDrag() {
    if (!dragging) return;
    dragging = false;
    document.removeEventListener('mousemove', onDrag);
    document.removeEventListener('mouseup', stopDrag);
    saveBoxState();
  }
  header.addEventListener('click', (e) => {
    if (box.dataset.collapsed !== '1') return;
    e.preventDefault();
    e.stopPropagation();
    openCollapsedBox();
  });

  // Resizing
  let resizing = false;
  let startW = 0, startH = 0, startX = 0, startY = 0, startLeft = 0;
  resizeHandle.addEventListener('mousedown', (e) => {
    e.stopPropagation();
    resizing = true;
    const rect = box.getBoundingClientRect();
    startW = rect.width; startH = rect.height; startX = e.clientX; startY = e.clientY; startLeft = rect.left;
    document.addEventListener('mousemove', onResize);
    document.addEventListener('mouseup', stopResize);
  });
  function onResize(e) {
    if (!resizing) return;
    let w = Math.max(100, startW - (e.clientX - startX));
    let h = Math.max(50, startH + (e.clientY - startY));
    w = Math.min(startLeft + startW, w);
    h = Math.min(window.innerHeight - box.getBoundingClientRect().top, h);
    const nextLeft = startLeft + startW - w;
    box.style.left = nextLeft + 'px';
    box.style.width = w + 'px';
    box.style.height = h + 'px';
  }
  function stopResize() {
    if (!resizing) return;
    resizing = false;
    document.removeEventListener('mousemove', onResize);
    document.removeEventListener('mouseup', stopResize);
    saveBoxState();
  }

  bottomResizeHandle.addEventListener('mousedown', (e) => {
    e.stopPropagation();
    resizing = true;
    const rect = box.getBoundingClientRect();
    startW = rect.width; startH = rect.height; startX = e.clientX; startY = e.clientY; startLeft = rect.left;
    document.addEventListener('mousemove', onBottomResize);
    document.addEventListener('mouseup', stopBottomResize);
  });
  function onBottomResize(e) {
    if (!resizing) return;
    let h = Math.max(50, startH + (e.clientY - startY));
    h = Math.min(window.innerHeight - box.getBoundingClientRect().top, h);
    box.style.height = h + 'px';
  }
  function stopBottomResize() {
    if (!resizing) return;
    resizing = false;
    document.removeEventListener('mousemove', onBottomResize);
    document.removeEventListener('mouseup', stopBottomResize);
    saveBoxState();
  }

  rightResizeHandle.addEventListener('mousedown', (e) => {
    e.stopPropagation();
    resizing = true;
    const rect = box.getBoundingClientRect();
    startW = rect.width; startH = rect.height; startX = e.clientX; startY = e.clientY; startLeft = rect.left;
    document.addEventListener('mousemove', onRightResize);
    document.addEventListener('mouseup', stopRightResize);
  });
  function onRightResize(e) {
    if (!resizing) return;
    let w = Math.max(100, startW + (e.clientX - startX));
    let h = Math.max(50, startH + (e.clientY - startY));
    w = Math.min(window.innerWidth - startLeft, w);
    h = Math.min(window.innerHeight - box.getBoundingClientRect().top, h);
    box.style.width = w + 'px';
    box.style.height = h + 'px';
  }
  function stopRightResize() {
    if (!resizing) return;
    resizing = false;
    document.removeEventListener('mousemove', onRightResize);
    document.removeEventListener('mouseup', stopRightResize);
    saveBoxState();
  }

  // Touch support
  header.addEventListener('touchstart', (e) => {
    if (box.dataset.collapsed === '1') return;
    const t = e.touches[0];
    dragging = true;
    movedWhileDragging = false;
    dragStartX = t.clientX;
    dragStartY = t.clientY;
    const rect = box.getBoundingClientRect();
    dragOffsetX = t.clientX - rect.left;
    dragOffsetY = t.clientY - rect.top;
  });
  document.addEventListener('touchmove', (e) => {
    if (!dragging) return;
    const t = e.touches[0];
    onDrag({ clientX: t.clientX, clientY: t.clientY });
  });
  document.addEventListener('touchend', () => { if (dragging) { dragging = false; saveBoxState(); } });
}

function saveBoxState() {
  try {
    const box = document.getElementById('black-box');
    if (!box) return;
    const isCollapsed = box.dataset.collapsed === '1';
    const state = {
      left: box.style.left,
      top: box.style.top,
      width: isCollapsed ? (box.dataset.expandedWidth || '360px') : box.style.width,
      height: isCollapsed ? (box.dataset.expandedHeight || '300px') : box.style.height
    };
    localStorage.setItem('aiBoxState', JSON.stringify(state));
  } catch (err) {}
}

function injectCondraUiStyles() {
  if (document.getElementById("condra-ui-styles")) return;
  const style = document.createElement("style");
  style.id = "condra-ui-styles";
  style.textContent = `
    #black-box * {
      box-sizing: border-box;
    }

    #black-box-content::-webkit-scrollbar {
      width: 8px;
    }

    #black-box-content::-webkit-scrollbar-track {
      background: transparent;
    }

    #black-box-content::-webkit-scrollbar-thumb {
      background: rgba(255,255,255,0.20);
      border-radius: 999px;
      border: 2px solid rgba(13,14,17,0.96);
    }

    #black-box-close:hover {
      background: rgba(255,255,255,0.12) !important;
      border-color: rgba(255,255,255,0.28) !important;
      color: #ffffff !important;
    }

    #black-box-brand {
      user-select: none;
    }

    #black-box-button-label {
      box-shadow: 0 10px 30px rgba(48, 210, 117, 0.28), inset 0 1px 0 rgba(255,255,255,0.45);
    }

    .condra-summary-card {
      background: rgba(255,255,255,0.065);
      border: 1px solid rgba(255,255,255,0.10);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.045), 0 8px 18px rgba(0,0,0,0.12);
    }

    .condra-summary-point {
      color: #f7f9fc;
      font-size: 14px;
      font-weight: 600;
      line-height: 1.45;
      letter-spacing: 0;
    }

    .condra-excerpt-line {
      color: rgba(244,247,251,0.78);
      background: rgba(244, 190, 86, 0.10);
      border-left-color: #f4be56 !important;
      font-size: 13px;
      line-height: 1.45;
    }

    .condra-draft-line {
      color: rgba(244,247,251,0.86);
      background: rgba(158, 228, 147, 0.08);
      font-size: 13px;
      line-height: 1.45;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    .condra-terminal-row {
      padding: 8px 10px;
      background: rgba(0,0,0,0.22);
      border: 1px solid rgba(255,255,255,0.10);
      border-radius: 8px;
      font-size: 14px;
      line-height: 1.35;
    }

    .condra-terminal-row input::placeholder {
      color: rgba(244,247,251,0.42);
    }

    .condra-quick-actions {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 7px;
      margin-bottom: 10px;
    }

    .condra-quick-button {
      min-width: 0;
      border: 1px solid rgba(255,255,255,0.10);
      border-radius: 8px;
      background: rgba(255,255,255,0.060);
      color: rgba(244,247,251,0.82);
      padding: 7px 6px;
      font: 750 12px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial;
      cursor: pointer;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .condra-quick-button:hover {
      background: rgba(255,255,255,0.10);
      color: #ffffff;
    }

    .condra-quick-button.active {
      background: rgba(158, 228, 147, 0.16);
      border-color: rgba(158, 228, 147, 0.36);
      color: #dff8dd;
    }

    .condra-ask-form {
      display: grid;
      gap: 10px;
      margin-top: 8px;
      padding: 11px;
      border: 1px solid rgba(255,255,255,0.10);
      border-radius: 8px;
      background: rgba(255,255,255,0.060);
    }

    .condra-check-row {
      display: flex;
      align-items: center;
      gap: 8px;
      color: rgba(244,247,251,0.74);
      font: 650 12px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial;
    }

    .condra-check-row input {
      width: 14px;
      height: 14px;
      accent-color: #9ee493;
    }

    .condra-ref-list {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin-top: 10px;
    }

    .condra-ref-button {
      max-width: 100%;
      border: 1px solid rgba(158, 228, 147, 0.30);
      border-radius: 999px;
      background: rgba(158, 228, 147, 0.09);
      color: #dff8dd;
      padding: 6px 9px;
      font: 600 12px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial;
      cursor: pointer;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .condra-ref-button:hover {
      background: rgba(158, 228, 147, 0.18);
      border-color: rgba(158, 228, 147, 0.55);
    }

    .condra-note-form {
      display: grid;
      gap: 10px;
      margin-top: 8px;
      padding: 11px;
      border: 1px solid rgba(255,255,255,0.10);
      border-radius: 8px;
      background: rgba(255,255,255,0.060);
    }

    .condra-note-form-title {
      color: #f7f9fc;
      font: 700 14px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial;
      line-height: 1.3;
    }

    .condra-note-label {
      display: grid;
      gap: 5px;
      color: rgba(244,247,251,0.66);
      font: 700 12px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial;
    }

    .condra-note-input,
    .condra-note-textarea {
      width: 100%;
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 7px;
      background: rgba(0,0,0,0.22);
      color: #f7f9fc;
      padding: 8px 9px;
      font: 500 13px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial;
      line-height: 1.35;
      outline: none;
    }

    .condra-note-input:focus,
    .condra-note-textarea:focus {
      border-color: rgba(158, 228, 147, 0.55);
      box-shadow: 0 0 0 3px rgba(158, 228, 147, 0.12);
    }

    .condra-note-textarea {
      min-height: 78px;
      resize: vertical;
    }

    .condra-note-actions {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
      align-items: center;
    }

    .condra-note-button {
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 7px;
      background: rgba(255,255,255,0.08);
      color: #f7f9fc;
      padding: 7px 10px;
      font: 700 12px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial;
      cursor: pointer;
    }

    .condra-note-button.primary {
      background: rgba(158, 228, 147, 0.18);
      border-color: rgba(158, 228, 147, 0.42);
      color: #dff8dd;
    }

    .condra-note-status {
      min-height: 18px;
      color: rgba(244,247,251,0.72);
      font: 600 12px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial;
    }

    .condra-notes-list {
      display: grid;
      gap: 8px;
      margin-top: 12px;
      padding-top: 10px;
      border-top: 1px solid rgba(255,255,255,0.10);
    }

    .condra-note-list-title {
      color: #f7f9fc;
      font: 700 13px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial;
    }

    .condra-note-list-empty {
      color: rgba(244,247,251,0.62);
      font: 500 12px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial;
    }

    .condra-note-list-item {
      display: grid;
      gap: 6px;
      padding: 9px;
      border: 1px solid rgba(255,255,255,0.09);
      border-radius: 8px;
      background: rgba(255,255,255,0.050);
    }

    .condra-note-list-main {
      color: rgba(244,247,251,0.88);
      font: 600 12px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }

    .condra-note-list-meta {
      color: rgba(244,247,251,0.55);
      font: 500 11px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }

    .condra-note-delete {
      justify-self: end;
      border: 1px solid rgba(255, 120, 120, 0.28);
      border-radius: 7px;
      background: rgba(255, 120, 120, 0.10);
      color: #ffd0d0;
      padding: 5px 8px;
      font: 700 11px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial;
      cursor: pointer;
    }

    .condra-note-related {
      display: grid;
      gap: 6px;
      margin-top: 4px;
      padding-top: 7px;
      border-top: 1px solid rgba(255,255,255,0.08);
    }

    .condra-note-related-title {
      color: rgba(244,247,251,0.70);
      font: 700 11px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial;
    }

    .condra-note-related-email {
      display: grid;
      gap: 3px;
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 7px;
      background: rgba(255,255,255,0.045);
      color: rgba(244,247,251,0.82);
      padding: 7px;
      text-align: left;
      cursor: pointer;
    }

    .condra-note-related-email-title {
      font: 700 11px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial;
      overflow-wrap: anywhere;
    }

    .condra-note-related-email-meta {
      color: rgba(244,247,251,0.55);
      font: 500 10px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial;
      overflow-wrap: anywhere;
    }
  `;
  document.documentElement.appendChild(style);
}

function loadBoxState() {
  try {
    const s = localStorage.getItem('aiBoxState');
    if (!s) {
      localStorage.setItem('aiBoxDefaultedTopRight', '1');
      return;
    }
    const state = JSON.parse(s);
    const box = document.getElementById('black-box');
    if (!box) return;
    if (localStorage.getItem('aiBoxDefaultedTopRight') !== '1') {
      localStorage.setItem('aiBoxDefaultedTopRight', '1');
      return;
    }
    if (state.width) box.style.width = state.width;
    if (state.height) box.style.height = state.height;
  } catch (err) {}
}
function extractEmailFromString(s) {
  if (!s) return null;
  const m = s.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
  return m ? m[0] : null;
}

function isVisible(el) {
  try {
    if (!el) return false;
    if (!(el instanceof HTMLElement)) return false;
    const r = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return !!(r.width || r.height) && style.display !== "none" && style.visibility !== "hidden" && style.opacity !== "0";
  } catch (err) {
    return false;
  }
}

function isCondraMailHost() {
  const host = location.hostname;
  return host.includes("mail.google.com") || host.includes("outlook.live.com") || host.includes("outlook.office.com");
}

function isCondraOutlookHost() {
  const host = location.hostname;
  return host.includes("outlook.live.com") || host.includes("outlook.office.com");
}

function getGmailEmail() {
  try {
    if (isCondraOutlookHost()) {
      const savedOutlookEmail = String(localStorage.getItem("condraOutlookAccount") || "").trim();
      if (extractEmailFromString(savedOutlookEmail)) return savedOutlookEmail;
      const accountSelectors = [
        'button[aria-label*="@"]',
        '[role="button"][aria-label*="@"]',
        'img[alt*="@"]',
        '[data-testid*="account"]',
        '[data-test-id*="account"]'
      ];
      for (const sel of accountSelectors) {
        const el = document.querySelector(sel);
        if (!el) continue;
        const text = el.getAttribute("aria-label") || el.getAttribute("alt") || el.getAttribute("title") || el.textContent || "";
        const e = extractEmailFromString(text);
        if (e) return e;
      }
      return CONDRA_DEFAULT_OUTLOOK_EMAIL;
    }

    // Common place: account button aria-label contains the email
    const acct = document.querySelector('[aria-label*="Google Account"]') || document.querySelector('a[aria-label*="Google Account"]');
    if (acct) {
      const aria = acct.getAttribute('aria-label') || acct.alt || acct.title || acct.textContent;
      const e = extractEmailFromString(aria);
      if (e) return e;
    }

    // Profile image alt text sometimes contains the email
    const img = document.querySelector('img[alt*="@"]');
    if (img) {
      const e = extractEmailFromString(img.alt);
      if (e) return e;
    }

    // Search common header/profile areas for email text (limited scope)
    const headerAreas = Array.from(document.querySelectorAll('header, div[role="navigation"], div[role="banner"], div[gh]'));
    for (const area of headerAreas) {
      const candidate = area.querySelector('[email], img[alt*="@"], [aria-label*="@"], a[href^="mailto:"]');
      if (candidate) {
        const text = candidate.getAttribute('email') || candidate.alt || candidate.getAttribute('aria-label') || candidate.getAttribute('href') || candidate.textContent;
        const e = extractEmailFromString(text);
        if (e) return e;
      }
    }

    // Fallback: some Gmail globals contain email (best-effort)
    if (window.GLOBALS && Array.isArray(window.GLOBALS)) {
      for (const g of window.GLOBALS) {
        const e = extractEmailFromString(String(g));
        if (e) return e;
      }
    }
  } catch (err) {
    // ignore
  }
  return null;
}

const CONDRA_LOCAL_BASES = [
  "http://127.0.0.1:5050",
  "http://localhost:5050",
  "http://127.0.0.1:5000",
  "http://localhost:5000",
  "http://2.25.188.4"
];
const CONDRA_DEFAULT_OUTLOOK_EMAIL = "heparknew111@outlook.com";
const CONDRA_SUMMARY_CACHE_MS = 30000;
const CONDRA_NOTES_CACHE_MS = 5 * 60 * 1000;
const CONDRA_MATCH_CACHE_MS = 10 * 60 * 1000;
const CONDRA_LABEL_SYNC_CACHE_MS = 0;
let condraSummaryCache = { userEmail: "", fetchedAt: 0, items: [] };
let condraLastLabelSync = { userEmail: "", base: "", syncedAt: 0 };
let condraAiBoxRequestId = 0;
let condraLastFetchInfo = { userEmail: "", base: "", count: 0, error: "" };
let condraApplyingHighlights = false;
let condraCurrentSummary = null;
let condraCurrentEmailText = "";
let condraCurrentSubjectText = "";
let condraAskDraft = null;

function isCondraSignInError(value) {
  const text = String(value || "").toLowerCase();
  return text.includes("sign in")
    || text.includes("missing_user")
    || text.includes("session_required")
    || text.includes("reauth_required")
    || text.includes("extension_auth_required")
    || text.includes("no saved")
    || text.includes("no supabase token");
}

function condraFriendlyError(value) {
  return isCondraSignInError(value) ? "Sign in" : String(value || "Could not reach local Condra server.");
}

function normalizeForCondraMatch(value) {
  return String(value || "")
    .replace(/[""]/g, '"')
    .replace(/['']/g, "'")
    .replace(/\s+/g, " ")
    .replace(/^((re|fw|fwd):\s*)+/i, "")
    .trim()
    .toLowerCase();
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function condraCacheKey(kind, userEmail, extra = "") {
  return `condra:${kind}:${String(userEmail || "").toLowerCase()}:${extra}`;
}

function readCondraStoredCache(key, maxAgeMs) {
  try {
    const cached = JSON.parse(localStorage.getItem(key) || "null");
    if (!cached || Date.now() - Number(cached.savedAt || 0) > maxAgeMs) return null;
    return cached.value;
  } catch (err) {
    return null;
  }
}

function writeCondraStoredCache(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify({ savedAt: Date.now(), value }));
  } catch (err) {
    console.debug("content.js: could not write Condra cache", err);
  }
}

function removeCondraStoredCache(key) {
  try {
    localStorage.removeItem(key);
  } catch (err) {
    // ignore
  }
}

function condraMatchCacheExtra(subject, snippet, timeText) {
  return JSON.stringify([
    normalizeForCondraMatch(subject),
    normalizeForCondraMatch(String(snippet || "").slice(0, 500))
  ]);
}

function parseCondraSummary(raw) {
  const result = {
    id: "",
    subject: "",
    sender: "",
    time: "",
    objectiveId: "",
    objectiveInfo: "",
    objectiveCompletion: "",
    bullets: [],
    excerpts: [],
    bodyText: ""
  };

  const jsonStart = raw.indexOf("{");
  if (jsonStart !== -1) {
    let inString = false;
    let escape = false;
    let depth = 0;
    for (let i = jsonStart; i < raw.length; i++) {
      const ch = raw[i];
      if (ch === '"' && !escape) inString = !inString;
      if (!inString) {
        if (ch === "{") depth++;
        if (ch === "}") depth--;
        if (depth === 0) {
          try {
            const cleanedJson = raw.slice(jsonStart, i + 1)
              .replace(/“|”/g, '"')
              .replace(/’/g, "'")
              .replace(/\n/g, " ")
              .replace(/\r/g, "");
            const parsed = JSON.parse(cleanedJson);
            if (Array.isArray(parsed.bullets)) {
              result.bullets = parsed.bullets.map((b) => ({
                point: String((b && b.point) || "").trim(),
                excerpt: String((b && b.excerpt) || "").trim()
              })).filter((b) => b.point || b.excerpt);
              result.excerpts = result.bullets.map((b) => b.excerpt).filter(Boolean);
            }
            result.objectiveId = String(parsed["is Objective"] || "").trim();
            result.objectiveInfo = String(parsed["info about Objective"] || "").trim();
            result.objectiveCompletion = String(parsed["completion of objective"] || "").trim();
          } catch (err) {
            console.debug("content.js: Condra summary JSON parse failed", err);
          }
          break;
        }
      }
      escape = ch === "\\" && !escape;
      if (ch !== "\\") escape = false;
    }
  }

  raw.split("\n").forEach((line) => {
    const clean = line.trim();
    if (clean.startsWith("ID:")) result.id = clean.replace("ID:", "").trim();
    if (clean.startsWith("Time:")) result.time = clean.replace("Time:", "").trim();
    if (clean.startsWith("Subject:")) result.subject = clean.replace("Subject:", "").trim();
    if (clean.startsWith("From:")) result.sender = clean.replace("From:", "").trim();
  });
  const bodyMatch = String(raw || "").match(/\nBody:\s*([\s\S]*?)(?:\n0\s*$|$)/i);
  result.bodyText = bodyMatch ? bodyMatch[1].trim() : "";

  return result;
}

function condraMatchTokens(value) {
  const stop = new Set(["the", "and", "for", "you", "your", "that", "this", "with", "from", "have", "are", "was", "were", "will", "can", "email", "please", "thanks", "hello"]);
  return new Set((normalizeForCondraMatch(value).match(/[a-z0-9]{4,}/g) || []).filter((token) => !stop.has(token)));
}

function condraTokenOverlap(left, right) {
  const a = condraMatchTokens(left);
  const b = condraMatchTokens(right);
  if (!a.size || !b.size) return 0;
  let overlap = 0;
  a.forEach((token) => {
    if (b.has(token)) overlap += 1;
  });
  return overlap;
}

function condraSummaryMatchesOpenEmail(subject, snippet, messageId, summary, response = {}) {
  if (!summary) return false;
  const responseId = String((response && response.email_id) || (summary && summary.id) || "").trim();
  const openId = String(messageId || "").trim();
  if (openId && responseId && openId === responseId) return true;

  const openSubject = normalizeForCondraMatch(subject || "");
  const summarySubject = normalizeForCondraMatch((summary && summary.subject) || "");
  let score = 0;
  if (openSubject && summarySubject) {
    if (openSubject === summarySubject) score += 30;
    else if (openSubject.includes(summarySubject) || summarySubject.includes(openSubject)) score += 12;
    else return false;
  }

  const openBody = String(snippet || "");
  const summaryBody = String((summary && summary.bodyText) || "");
  const bodySample = normalizeForCondraMatch(openBody).slice(0, 700);
  const summaryNorm = normalizeForCondraMatch(summaryBody);
  if (bodySample && bodySample.length >= 80 && summaryNorm.includes(bodySample)) {
    score += 100;
  } else {
    score += Math.min(80, condraTokenOverlap(openBody, summaryBody) * 4);
  }
  return score >= 45 || (openSubject && summarySubject && score >= 30 && condraTokenOverlap(openBody, summaryBody) >= 2);
}

async function fetchCondraSummaries() {
  const userEmail = getGmailEmail();
  condraLastFetchInfo = { userEmail: userEmail || "", base: "", count: 0, error: "" };
  if (!userEmail) {
    condraLastFetchInfo.error = "Could not detect signed-in Gmail account.";
    return [];
  }

  const now = Date.now();
  if (
    condraSummaryCache.userEmail === userEmail &&
    now - condraSummaryCache.fetchedAt < CONDRA_SUMMARY_CACHE_MS
  ) {
    return condraSummaryCache.items;
  }

  for (const base of CONDRA_LOCAL_BASES) {
    try {
      const url = `${base}/extension/summaries?user_email=${encodeURIComponent(userEmail)}&t=${Date.now()}`;
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) continue;
      const text = await res.text();
      const items = text
        .split("\n---\n")
        .map((chunk) => chunk.trim())
        .filter(Boolean)
        .map(parseCondraSummary);
      condraSummaryCache = { userEmail, fetchedAt: now, items };
      condraLastFetchInfo = { userEmail, base, count: items.length, error: "" };
      return items;
    } catch (err) {
      condraLastFetchInfo = { userEmail, base, count: 0, error: String(err && err.message || err) };
      console.debug("content.js: could not fetch Condra summaries from", base, err);
    }
  }

  return [];
}

async function printCondraRecentEmailsInFlask() {
  const userEmail = getGmailEmail();
  let lastError = "";

  for (const base of CONDRA_LOCAL_BASES) {
    try {
      const url = `${base}/extension/print_recent_emails?user_email=${encodeURIComponent(userEmail || "")}&t=${Date.now()}`;
      const res = await fetch(url, { cache: "no-store" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        lastError = data.message || `Print recent emails failed (${res.status})`;
        continue;
      }
      return data;
    } catch (err) {
      lastError = String(err && err.message || err);
    }
  }

  throw new Error(lastError || "Could not reach local Condra server.");
}

async function fetchCondraSummaryLikeSuperTest(subject, snippet, timeText, messageId = "") {
  const userEmail = getGmailEmail();
  if (!userEmail) return null;
  const cacheKey = condraCacheKey("match", userEmail, JSON.stringify([
    normalizeForCondraMatch(subject),
    normalizeForCondraMatch(String(snippet || "").slice(0, 500))
  ]));
  const useBrowserMatchCache = !isCondraOutlookHost();
  const cachedMatch = useBrowserMatchCache ? readCondraStoredCache(cacheKey, CONDRA_MATCH_CACHE_MS) : null;
  if (cachedMatch !== null) {
    condraLastFetchInfo = {
      userEmail,
      base: "browser cache",
      count: cachedMatch ? 1 : 0,
      error: "",
      matchedBy: "cache"
    };
    return cachedMatch;
  }

  let lastMatchError = "";
  for (const base of CONDRA_LOCAL_BASES) {
    try {
      const res = await fetch(`${base}/extension/match_summary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        body: JSON.stringify({
          user_email: userEmail,
          subject: subject || "",
          snippet: String(snippet || "").slice(0, 1600)
        })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        lastMatchError = condraFriendlyError(data && (data.message || data.error));
        if (lastMatchError !== "Sign in") {
          lastMatchError = `${base}/extension/match_summary failed (${res.status})${lastMatchError ? `: ${lastMatchError}` : ""}`;
        }
        console.warn("[Condra] match_summary failed", { base, status: res.status, data });
        continue;
      }
      if (!data || !data.found) {
        const friendlyMessage = condraFriendlyError(data && (data.message || data.error));
        lastMatchError = friendlyMessage === "Sign in"
          ? "Sign in"
          : data && (data.message || data.error)
          ? `${base}: ${friendlyMessage}`
          : `${base}: no saved summary found`;
        console.info("[Condra] match_summary found no summary", { base, data });
        continue;
      }
      condraLastFetchInfo = {
        userEmail,
        base,
        count: data.match_count || 1,
        error: "",
        matchedBy: data.matched_by || ""
      };
      console.log("[Condra] match_summary response", data);
      if (data.summary) {
        const summary = data.summary;
        if (data.raw_chunk && !summary.bodyText) {
          const rawParsed = parseCondraSummary(String(data.raw_chunk || ""));
          summary.bodyText = rawParsed.bodyText || "";
          summary.id = summary.id || rawParsed.id || "";
        }
        if (!condraSummaryMatchesOpenEmail(subject, snippet, messageId, summary, data)) {
          condraLastFetchInfo.error = "Matched summary did not match the open email.";
          continue;
        }
        if (useBrowserMatchCache) writeCondraStoredCache(cacheKey, summary);
        return summary;
      }
      if (!data.raw_chunk) continue;
      const parsed = parseCondraSummary(String(data.raw_chunk || ""));
      if (!condraSummaryMatchesOpenEmail(subject, snippet, messageId, parsed, data)) {
        condraLastFetchInfo.error = "Matched summary did not match the open email.";
        continue;
      }
      if (useBrowserMatchCache) writeCondraStoredCache(cacheKey, parsed);
      return parsed;
    } catch (err) {
      condraLastFetchInfo = { userEmail, base, count: 0, error: String(err && err.message || err) };
      const friendlyMessage = condraFriendlyError(condraLastFetchInfo.error);
      lastMatchError = friendlyMessage === "Sign in" ? "Sign in" : `${base}/extension/match_summary: ${friendlyMessage}`;
      console.debug("content.js: could not match Condra summary like superTest", err);
    }
  }

  condraLastFetchInfo = {
    userEmail,
    base: "",
    count: 0,
    error: lastMatchError || "No saved summary matched the open email."
  };
  writeCondraStoredCache(cacheKey, null);
  return null;
}

async function askCondraAi(question, useEmailContext) {
  const userEmail = getGmailEmail();
  const bodyRoot = useEmailContext ? getOpenMessageBodyRoot() : null;
  const currentEmail = useEmailContext ? {
    id: isCondraOutlookHost() ? getOutlookMessageIdFromLocation() : "",
    user_email: userEmail || "",
    url: location.href,
    sender: condraCurrentEmailText || "",
    subject: condraCurrentSubjectText || "",
    body: bodyRoot ? bodyRoot.innerText.trim() : ""
  } : null;
  let lastError = "";

  for (const base of CONDRA_LOCAL_BASES) {
    try {
      const res = await fetch(`${base}/extension/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_email: userEmail || "",
          question,
          context_mode: useEmailContext ? "current_email" : "chat",
          use_email_context: !!useEmailContext,
          current_email: currentEmail
        })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        lastError = condraFriendlyError(data.message || data.error || `Ask failed (${res.status})`);
        continue;
      }
      return data;
    } catch (err) {
      lastError = condraFriendlyError(err && err.message || err);
    }
  }

  throw new Error(condraFriendlyError(lastError));
}

async function saveCondraNote(topic, expectedFrom, aiActionText) {
  const userEmail = getGmailEmail();
  const aiAction = String(aiActionText || "").trim();
  let lastError = "";

  for (const base of CONDRA_LOCAL_BASES) {
    try {
      const res = await fetch(`${base}/extension/save_note`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_email: userEmail || "",
          topic,
          expected_from: expectedFrom,
          ai_action: aiAction
        })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        lastError = data.message || `Save note failed (${res.status})`;
        continue;
      }
      removeCondraStoredCache(condraCacheKey("notes", userEmail || ""));
      return data;
    } catch (err) {
      lastError = String(err && err.message || err);
    }
  }

  throw new Error(lastError || "Could not reach local Condra server.");
}

async function fetchCondraNotes() {
  const userEmail = getGmailEmail();
  const notesCacheKey = condraCacheKey("notes", userEmail || "");

  let lastError = "";

  for (const base of CONDRA_LOCAL_BASES) {
    try {
      const now = Date.now();
      const shouldSyncLabels = (
        condraLastLabelSync.userEmail !== (userEmail || "") ||
        condraLastLabelSync.base !== base ||
        now - condraLastLabelSync.syncedAt > CONDRA_LABEL_SYNC_CACHE_MS
      );
      if (shouldSyncLabels) {
        await fetch(`${base}/extension/sync_note_labels`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          cache: "no-store",
          body: JSON.stringify({ user_email: userEmail || "" })
        }).catch(() => null);
        await fetch(`${base}/extension/sync_objective_email_labels`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          cache: "no-store",
          body: JSON.stringify({ user_email: userEmail || "" })
        }).catch(() => null);
        condraLastLabelSync = { userEmail: userEmail || "", base, syncedAt: now };
      }
      const cachedNotes = readCondraStoredCache(notesCacheKey, CONDRA_NOTES_CACHE_MS);
      if (cachedNotes && !shouldSyncLabels) return cachedNotes;
      const url = `${base}/extension/notes?user_email=${encodeURIComponent(userEmail || "")}&t=${Date.now()}`;
      const res = await fetch(url, { cache: "no-store" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        lastError = data.message || `Load notes failed (${res.status})`;
        continue;
      }
      writeCondraStoredCache(notesCacheKey, data);
      return data;
    } catch (err) {
      lastError = String(err && err.message || err);
    }
  }

  throw new Error(lastError || "Could not reach local Condra server.");
}

async function deleteCondraNote(index) {
  const userEmail = getGmailEmail();
  let lastError = "";

  for (const base of CONDRA_LOCAL_BASES) {
    try {
      const res = await fetch(`${base}/extension/delete_note`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_email: userEmail || "",
          index
        })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        lastError = data.message || `Delete note failed (${res.status})`;
        continue;
      }
      removeCondraStoredCache(condraCacheKey("notes", userEmail || ""));
      return data;
    } catch (err) {
      lastError = String(err && err.message || err);
    }
  }

  throw new Error(lastError || "Could not reach local Condra server.");
}

async function postCondraAction(path, body) {
  const userEmail = getGmailEmail();
  let lastError = "";

  for (const base of CONDRA_LOCAL_BASES) {
    try {
      const res = await fetch(`${base}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_email: userEmail || "",
          ...body
        })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (data && data.error === "reauth_required") {
          const err = new Error(data.message || "Please reconnect Google permissions.");
          err.reauthRequired = true;
          err.reauthUrl = `${base}/sign`;
          throw err;
        }
        lastError = data.message || data.error || `${path} failed (${res.status})`;
        continue;
      }
      return data;
    } catch (err) {
      lastError = String(err && err.message || err);
    }
  }

  throw new Error(lastError || "Could not reach local Condra server.");
}

function findMatchingCondraSummary(items, openSubject, openSenderEmail) {
  const normalizedOpenSubject = normalizeForCondraMatch(openSubject);
  if (!normalizedOpenSubject) return null;

  let best = null;
  let bestScore = 0;
  for (const item of items) {
    if (!item.bullets.length && !item.excerpts.length) continue;

    const itemSubject = normalizeForCondraMatch(item.subject);
    let score = 0;
    if (itemSubject === normalizedOpenSubject) score += 4;
    else if (itemSubject && (itemSubject.includes(normalizedOpenSubject) || normalizedOpenSubject.includes(itemSubject))) score += 2;

    const itemSenderEmail = extractEmailFromString(item.sender);
    if (openSenderEmail && itemSenderEmail && openSenderEmail.toLowerCase() === itemSenderEmail.toLowerCase()) {
      score += 2;
    }

    if (score > bestScore) {
      best = item;
      bestScore = score;
    }
  }

  return bestScore >= 2 ? best : null;
}

function appendBoxLine(parent, text, styles = {}) {
  const div = document.createElement("div");
  div.textContent = text;
  Object.assign(div.style, styles);
  parent.appendChild(div);
  return div;
}

function appendThinkingLine(parent) {
  const line = appendBoxLine(parent, "Thinking", {
    color: "rgba(244,247,251,0.72)",
    marginTop: "8px",
    fontFamily: "Menlo, Consolas, monospace"
  });
  let dotCount = 0;
  const timer = window.setInterval(() => {
    dotCount = (dotCount + 1) % 4;
    line.textContent = `Thinking${".".repeat(dotCount)}`;
  }, 320);

  return () => {
    window.clearInterval(timer);
    line.remove();
  };
}

function typeTextIntoLine(line, text, delayMs = 14) {
  return new Promise((resolve) => {
    const value = String(text || "");
    let index = 0;
    line.textContent = "";

    function tick() {
      const chunkSize = value.length > 800 ? 4 : 2;
      line.textContent += value.slice(index, index + chunkSize);
      index += chunkSize;
      line.scrollIntoView({ block: "end" });

      if (index >= value.length) {
        resolve();
        return;
      }
      window.setTimeout(tick, delayMs);
    }

    tick();
  });
}

function getCurrentGmailAccountPath() {
  const match = location.pathname.match(/\/mail\/u\/[^/]+/);
  return match ? match[0] : "/mail/u/0";
}

function openGmailMessageRef(ref) {
  const webLink = String((ref && (ref.web_link || ref.url)) || "").trim();
  if (webLink) {
    window.open(webLink, "_blank", "noopener,noreferrer");
    return;
  }
  if (isCondraOutlookHost()) {
    const subject = String((ref && ref.subject) || "").trim();
    if (subject) {
      window.open(`https://outlook.live.com/mail/0/search?q=${encodeURIComponent(subject)}`, "_blank", "noopener,noreferrer");
      return;
    }
  }
  const id = String((ref && (ref.web_id || ref.thread_id || ref.id)) || "").trim();
  if (!id) return;
  const base = `${location.origin}${getCurrentGmailAccountPath()}/#all/`;
  window.open(base + encodeURIComponent(id), "_blank", "noopener,noreferrer");
}

function appendObjectiveCompletionPreview(parent, summary) {
  const objectiveCompletion = String(summary && summary.objectiveCompletion || "").trim();
  if (!objectiveCompletion || objectiveCompletion.toLowerCase() === "none") return;

  const line = appendBoxLine(parent, `Objective completion:\n${objectiveCompletion}`, {
    marginTop: "8px",
    padding: "8px 10px",
    borderLeft: "3px solid #9ee493",
    borderRadius: "8px",
    whiteSpace: "pre-wrap"
  });
  line.className = "condra-draft-line";
}

function appendAskRefs(parent, refs) {
  if (!Array.isArray(refs) || refs.length === 0) return;

  const list = document.createElement("div");
  list.className = "condra-ref-list";

  refs.slice(0, 6).forEach((ref) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "condra-ref-button";
    button.textContent = ref && ref.subject ? ref.subject : "(No Subject)";
    button.title = "Open source email";
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      openGmailMessageRef(ref);
    });
    list.appendChild(button);
  });

  parent.appendChild(list);
}

function stopCondraInputEvents(el) {
  ["click", "mousedown", "keydown", "keyup", "keypress", "input", "change"].forEach((eventName) => {
    el.addEventListener(eventName, (event) => event.stopPropagation());
  });
}

function makeCondraNoteField(labelText, field) {
  const label = document.createElement("label");
  label.className = "condra-note-label";
  label.textContent = labelText;
  label.appendChild(field);
  return label;
}

function cleanCondraAiAction(rawAiAction) {
  return String(rawAiAction || "").trim();
}

function getCondraNoteDisplay(note) {
  if (typeof note === "string") {
    return { main: note, meta: "" };
  }

  const topic = String(note && note.topic || "").trim();
  const expectedFrom = String(note && note.expected_from || "").trim();
  const aiAction = cleanCondraAiAction(note && note.ai_action);
  const text = String(note && note.text || "").trim();
  const createdAt = String(note && note.created_at || "").trim();
  const main = topic || text || "Untitled note";
  const metaParts = [];
  if (expectedFrom) metaParts.push(`From: ${expectedFrom}`);
  if (aiAction) metaParts.push(`AI: ${aiAction}`);
  if (createdAt) {
    const parsed = new Date(createdAt);
    metaParts.push(Number.isNaN(parsed.getTime()) ? `Saved: ${createdAt}` : `Saved: ${parsed.toLocaleString()}`);
  }
  return { main, meta: metaParts.join(" | ") };
}

function getCondraNoteObjectiveKey(note) {
  return String(note && typeof note === "object" && note.objective_key || "").trim();
}

function findCondraNoteForSummary(summary, notes) {
  const objectiveId = String(summary && summary.objectiveId || "").trim();
  if (!objectiveId || !Array.isArray(notes)) return null;
  return notes.find((note) => getCondraNoteObjectiveKey(note) === objectiveId) || null;
}

function findCondraRelatedEmails(note, summaries) {
  const objectiveKey = getCondraNoteObjectiveKey(note);
  if (!objectiveKey || !Array.isArray(summaries)) return [];
  return summaries
    .filter((summary) => String(summary && summary.objectiveId || "").trim() === objectiveKey)
    .sort((a, b) => {
      const aMs = Date.parse(String(a.time || ""));
      const bMs = Date.parse(String(b.time || ""));
      if (Number.isFinite(aMs) && Number.isFinite(bMs)) return bMs - aMs;
      return 0;
    });
}

function renderCondraRelatedEmails(parent, note, summaries) {
  const related = findCondraRelatedEmails(note, summaries);
  if (!related.length) return;

  const wrap = document.createElement("div");
  wrap.className = "condra-note-related";

  const title = document.createElement("div");
  title.className = "condra-note-related-title";
  title.textContent = "Relevant emails";
  wrap.appendChild(title);

  related.slice(0, 4).forEach((email) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "condra-note-related-email";

    const subject = document.createElement("div");
    subject.className = "condra-note-related-email-title";
    subject.textContent = email.subject || "No Subject";
    button.appendChild(subject);

    const meta = document.createElement("div");
    meta.className = "condra-note-related-email-meta";
    meta.textContent = `${email.sender || "Unknown sender"}${email.time ? ` | ${email.time}` : ""}`;
    button.appendChild(meta);

    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      openGmailMessageRef(email);
    });
    wrap.appendChild(button);
  });

  parent.appendChild(wrap);
}

async function loadCondraNotesList(list, status) {
  list.replaceChildren();

  const title = document.createElement("div");
  title.className = "condra-note-list-title";
  title.textContent = "Saved Notes";
  list.appendChild(title);

  try {
    const data = await fetchCondraNotes();
    const notes = Array.isArray(data.notes) ? data.notes : [];
    if (!notes.length) {
      const empty = document.createElement("div");
      empty.className = "condra-note-list-empty";
      empty.textContent = "No saved notes yet.";
      list.appendChild(empty);
      return;
    }

    notes.forEach((note, index) => {
      const item = document.createElement("div");
      item.className = "condra-note-list-item";

      const display = getCondraNoteDisplay(note);
      const main = document.createElement("div");
      main.className = "condra-note-list-main";
      main.textContent = display.main;
      item.appendChild(main);

      if (display.meta) {
        const meta = document.createElement("div");
        meta.className = "condra-note-list-meta";
        meta.textContent = display.meta;
        item.appendChild(meta);
      }

      const deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.className = "condra-note-delete";
      deleteButton.textContent = "Delete";
      deleteButton.addEventListener("click", async (event) => {
        event.preventDefault();
        event.stopPropagation();
        deleteButton.disabled = true;
        if (status) status.textContent = "Deleting note...";
        try {
          await deleteCondraNote(index);
          if (status) status.textContent = "Note deleted.";
          await loadCondraNotesList(list, status);
        } catch (err) {
          if (status) status.textContent = `Delete failed: ${String(err && err.message || err)}`;
          deleteButton.disabled = false;
        }
      });
      item.appendChild(deleteButton);

      list.appendChild(item);
    });
  } catch (err) {
    const empty = document.createElement("div");
    empty.className = "condra-note-list-empty";
    empty.textContent = `Could not load notes: ${String(err && err.message || err)}`;
    list.appendChild(empty);
  }
}

function renderCondraNoteForm(content) {
  content.replaceChildren();
  content.dataset.condraStatus = "note-form";

  const form = document.createElement("form");
  form.className = "condra-note-form";
  form.noValidate = true;

  const title = document.createElement("div");
  title.className = "condra-note-form-title";
  title.textContent = "Create Note";
  form.appendChild(title);

  const topic = document.createElement("input");
  topic.className = "condra-note-input";
  topic.type = "text";
  topic.placeholder = "e.g. Internship updates from NVIDIA";
  topic.value = condraCurrentSubjectText || "";
  stopCondraInputEvents(topic);
  form.appendChild(makeCondraNoteField("Topic of email", topic));

  const expectedFrom = document.createElement("input");
  expectedFrom.className = "condra-note-input";
  expectedFrom.type = "text";
  expectedFrom.placeholder = "e.g. recruiter@nvidia.com";
  expectedFrom.value = condraCurrentEmailText || "";
  stopCondraInputEvents(expectedFrom);
  form.appendChild(makeCondraNoteField("Who you expect it from", expectedFrom));

  const aiAction = document.createElement("textarea");
  aiAction.className = "condra-note-textarea";
  aiAction.placeholder = "What should AI do after this email arrives?";
  stopCondraInputEvents(aiAction);
  form.appendChild(makeCondraNoteField("AI action", aiAction));

  const status = document.createElement("div");
  status.className = "condra-note-status";
  form.appendChild(status);

  const actions = document.createElement("div");
  actions.className = "condra-note-actions";

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "condra-note-button";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    renderCondraTerminalBox(content);
  });
  actions.appendChild(cancel);

  const save = document.createElement("button");
  save.type = "submit";
  save.className = "condra-note-button primary";
  save.textContent = "Save Note";
  actions.appendChild(save);
  form.appendChild(actions);

  const list = document.createElement("div");
  list.className = "condra-notes-list";
  form.appendChild(list);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    event.stopPropagation();

    const topicValue = topic.value.trim();
    const expectedFromValue = expectedFrom.value.trim();
    const aiActionValue = aiAction.value.trim();
    if (!topicValue || !expectedFromValue || !aiActionValue) {
      status.textContent = "Fill in topic, expected sender, and AI action.";
      return;
    }

    save.disabled = true;
    cancel.disabled = true;
    status.textContent = "Saving note...";
    try {
      const data = await saveCondraNote(topicValue, expectedFromValue, aiActionValue);
      status.textContent = `Saved for ${data.user_email || "your account"}.`;
      topic.value = "";
      expectedFrom.value = "";
      aiAction.value = "";
      await loadCondraNotesList(list, status);
      save.disabled = false;
      cancel.disabled = false;
      topic.focus();
    } catch (err) {
      status.textContent = `Save failed: ${String(err && err.message || err)}`;
      save.disabled = false;
      cancel.disabled = false;
    }
  });

  content.appendChild(form);
  appendCondraTerminalPrompt(content, { autofocus: false });
  loadCondraNotesList(list, status);
  window.setTimeout(() => (topic.value ? aiAction.focus() : topic.focus()), 0);
}

function appendCondraQuickActions(content, active = "") {
  const actions = document.createElement("div");
  actions.className = "condra-quick-actions";

  [
    ["summary", "Summary"],
    ["notes", "Notes"],
    ["ask", "Ask"],
    ["recent", "Recent"]
  ].forEach(([key, label]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `condra-quick-button${active === key ? " active" : ""}`;
    button.textContent = label;
    button.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();

      if (key === "summary") {
        renderCondraAiBox(content, condraCurrentEmailText, condraCurrentSubjectText, condraCurrentSummary);
        return;
      }

      if (key === "notes") {
        renderCondraNoteForm(content);
        return;
      }

      if (key === "ask") {
        renderCondraAskForm(content);
        return;
      }

      if (key === "recent") {
        await renderCondraRecentStatus(content);
      }
    });
    actions.appendChild(button);
  });

  content.appendChild(actions);
}

async function renderCondraRecentStatus(content) {
  content.replaceChildren();
  content.dataset.condraStatus = "recent";
  appendCondraQuickActions(content, "recent");
  const stopThinking = appendThinkingLine(content);
  try {
    const data = await printCondraRecentEmailsInFlask();
    stopThinking();
    appendBoxLine(content, `Printed ${data.count || 0} recent email(s) in the Flask terminal.`, {
      marginTop: "10px",
      color: "rgba(244,247,251,0.82)"
    });
  } catch (err) {
    stopThinking();
    appendBoxLine(content, `Print failed: ${String(err && err.message || err)}`, {
      marginTop: "10px",
      color: "rgba(244,247,251,0.82)"
    });
  }
  appendCondraTerminalPrompt(content, { autofocus: false });
}

function renderCondraAskForm(content) {
  content.replaceChildren();
  content.dataset.condraStatus = "ask";
  appendCondraQuickActions(content, "ask");

  const form = document.createElement("form");
  form.className = "condra-ask-form";
  form.noValidate = true;

  const title = document.createElement("div");
  title.className = "condra-note-form-title";
  title.textContent = "Ask Condra";
  form.appendChild(title);

  const question = document.createElement("textarea");
  question.className = "condra-note-textarea";
  question.placeholder = "Ask about this email, your saved emails, or what to do next...";
  stopCondraInputEvents(question);
  form.appendChild(question);

  const contextLabel = document.createElement("label");
  contextLabel.className = "condra-check-row";
  const context = document.createElement("input");
  context.type = "checkbox";
  context.checked = !!condraCurrentSummary || !!condraCurrentSubjectText;
  stopCondraInputEvents(context);
  const contextText = document.createElement("span");
  contextText.textContent = "Use current email context";
  contextLabel.appendChild(context);
  contextLabel.appendChild(contextText);
  form.appendChild(contextLabel);

  const status = document.createElement("div");
  status.className = "condra-note-status";
  form.appendChild(status);

  const actions = document.createElement("div");
  actions.className = "condra-note-actions";

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "condra-note-button";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    renderCondraTerminalBox(content);
  });
  actions.appendChild(cancel);

  const submit = document.createElement("button");
  submit.type = "submit";
  submit.className = "condra-note-button primary";
  submit.textContent = "Ask";
  actions.appendChild(submit);
  form.appendChild(actions);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    const value = question.value.trim();
    if (!value) {
      status.textContent = "Type a question first.";
      question.focus();
      return;
    }

    question.disabled = true;
    context.disabled = true;
    submit.disabled = true;
    cancel.disabled = true;
    status.textContent = "Thinking...";
    try {
      const data = await askCondraAi(value, context.checked);
      status.textContent = "";
      const answer = appendBoxLine(form, "", {
        marginTop: "8px",
        whiteSpace: "pre-wrap",
        fontSize: "14px",
        lineHeight: "1.5",
        color: "#f4f7fb"
      });
      await typeTextIntoLine(answer, data.answer || "(No answer)");
      appendAskRefs(form, data.refs);
    } catch (err) {
      const message = condraFriendlyError(err && err.message || err);
      status.textContent = message === "Sign in" ? "Sign in" : `Ask failed: ${message}`;
    } finally {
      question.disabled = false;
      context.disabled = false;
      submit.disabled = false;
      cancel.disabled = false;
    }
  });

  content.appendChild(form);
  appendCondraTerminalPrompt(content, { autofocus: false });
  window.setTimeout(() => question.focus(), 0);
}

function selectCondraSummaryIndex(index) {
  if (condraExtensionApi && condraExtensionApi.runtime && condraExtensionApi.runtime.sendMessage) {
    const sent = condraExtensionApi.runtime.sendMessage({
      type: "CONDRA_SELECT_SUMMARY_INDEX",
      index: Number(index)
    });
    if (sent && typeof sent.catch === "function") sent.catch(() => null);
  }

  const content = document.getElementById("black-box-content");
  if (!content) return;

  if (!content.querySelector(`[data-condra-summary-index="${index}"]`) && condraCurrentSummary) {
    renderCondraAiBox(content, condraCurrentEmailText, condraCurrentSubjectText, condraCurrentSummary);
  }

  content.querySelectorAll("[data-condra-summary-index]").forEach((el) => {
    el.style.outline = "";
    el.style.background = "";
  });

  const target = content.querySelector(`[data-condra-summary-index="${index}"]`);
  if (!target) return;

  target.scrollIntoView({ block: "center", behavior: "smooth" });
  target.style.outline = "2px solid #FFD700";
  target.style.background = "rgba(255, 215, 0, 0.14)";

  window.setTimeout(() => {
    target.style.outline = "";
    target.style.background = "";
  }, 2200);
}

function focusCondraEmailHighlight(index) {
  const target = document.querySelector(`span.condra-email-highlight[data-condra-summary-index="${index}"]`);
  if (!target) return false;

  target.scrollIntoView({ block: "center", behavior: "smooth" });
  const previousOutline = target.style.outline;
  const previousBoxShadow = target.style.boxShadow;
  target.style.outline = "2px solid #111";
  target.style.boxShadow = "0 0 0 4px rgba(255, 215, 0, 0.36)";

  window.setTimeout(() => {
    target.style.outline = previousOutline;
    target.style.boxShadow = previousBoxShadow;
  }, 1800);

  return true;
}

function appendCondraTerminalPrompt(content, options = {}) {
  const mode = options.mode || "command";
  const row = document.createElement("div");
  row.className = "condra-terminal-row";
  row.style.display = "flex";
  row.style.alignItems = "center";
  row.style.gap = "8px";
  row.style.fontFamily = "Menlo, Consolas, monospace";
  row.style.marginTop = "12px";
  content.appendChild(row);

  const prompt = document.createElement("span");
  prompt.textContent = ">";
  prompt.style.color = "#9ee493";
  prompt.style.fontWeight = "700";
  row.appendChild(prompt);

  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = options.placeholder || "/sum, /notes, /recent, or /ask";
  input.autocomplete = "off";
  input.spellcheck = false;
  input.style.flex = "1";
  input.style.minWidth = "0";
  input.style.border = "0";
  input.style.outline = "0";
  input.style.background = "transparent";
  input.style.color = "#f7f9fc";
  input.style.font = "inherit";
  input.style.fontSize = "14px";
  row.appendChild(input);

  ["click", "mousedown", "keydown", "keyup", "keypress"].forEach((eventName) => {
    input.addEventListener(eventName, (event) => event.stopPropagation());
  });

  input.addEventListener("keydown", async (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    event.stopPropagation();

    const command = input.value.trim().toLowerCase();
    if (mode === "ask-context") {
      content.dataset.condraStatus = "ask";
      if (command === "y" || command === "yes") {
        condraAskDraft = { useEmailContext: true };
      appendBoxLine(content, "Question:", { opacity: "0.78", marginTop: "8px" });
        appendCondraTerminalPrompt(content, { mode: "ask-question", placeholder: "Ask AI..." });
        return;
      }
      if (command === "n" || command === "no") {
        condraAskDraft = { useEmailContext: false };
        appendBoxLine(content, "Question:", { opacity: "0.78", marginTop: "8px" });
        appendCondraTerminalPrompt(content, { mode: "ask-question", placeholder: "Ask AI..." });
        return;
      }
      appendBoxLine(content, "Type y or n.", { opacity: "0.78", marginTop: "8px" });
      appendCondraTerminalPrompt(content, { mode: "ask-context", placeholder: "y/n" });
      return;
    }

    if (mode === "ask-question") {
      content.dataset.condraStatus = "ask";
      if (!input.value.trim()) {
        appendBoxLine(content, "Question cannot be blank.", { opacity: "0.78", marginTop: "8px" });
        appendCondraTerminalPrompt(content, { mode: "ask-question", placeholder: "Ask AI..." });
        return;
      }

      const useEmailContext = !!(condraAskDraft && condraAskDraft.useEmailContext);
      const question = input.value.trim();
      input.disabled = true;
      const stopThinking = appendThinkingLine(content);
      try {
        const data = await askCondraAi(question, useEmailContext);
        stopThinking();
        const answerLine = appendBoxLine(content, "", {
          marginTop: "8px",
          whiteSpace: "pre-wrap",
          fontSize: "14px",
          lineHeight: "1.5",
          color: "#f4f7fb"
        });
        await typeTextIntoLine(answerLine, data.answer || "(No answer)");
        appendAskRefs(content, data.refs);
      } catch (err) {
        stopThinking();
        const message = condraFriendlyError(err && err.message || err);
        appendBoxLine(content, message === "Sign in" ? "Sign in" : `Ask failed: ${message}`, {
          marginTop: "8px",
          opacity: "0.82"
        });
      } finally {
        condraAskDraft = null;
        appendCondraTerminalPrompt(content);
      }
      return;
    }

    if (command === "/sum") {
      renderCondraAiBox(content, condraCurrentEmailText, condraCurrentSubjectText, condraCurrentSummary);
      return;
    }

    if (command === "/notes") {
      renderCondraNoteForm(content);
      return;
    }

    if (command === "/recent" || command === "/last") {
      input.disabled = true;
      const stopThinking = appendThinkingLine(content);
      try {
        const data = await printCondraRecentEmailsInFlask();
        stopThinking();
        appendBoxLine(content, `Printed ${data.count || 0} recent email(s) in the Flask terminal.`, {
          opacity: "0.82",
          marginTop: "8px"
        });
      } catch (err) {
        stopThinking();
        appendBoxLine(content, `Print failed: ${String(err && err.message || err)}`, {
          opacity: "0.82",
          marginTop: "8px"
        });
      }
      appendCondraTerminalPrompt(content);
      return;
    }

    if (command === "/ask") {
      renderCondraAskForm(content);
      return;
    }

    renderCondraTerminalBox(content, command ? `Unknown command: ${command}` : "");
  });

  if (options.autofocus !== false) {
    window.setTimeout(() => input.focus(), 0);
  }
  return input;
}

function renderCondraTerminalBox(content, message = "") {
  content.replaceChildren();
  content.dataset.condraStatus = message === "Not viewing an email. Commands still work." ? "no-email" : (condraCurrentSummary ? "ready" : "no-summary");

  appendCondraQuickActions(content, "");

  if (message) {
    const friendly = message === "Not viewing an email. Commands still work."
      ? "Open an email to see its summary, or use Notes and Ask anytime."
      : message;
    appendBoxLine(content, friendly, { color: "rgba(244,247,251,0.72)", marginTop: "10px", marginBottom: "8px" });
  }

  appendCondraTerminalPrompt(content, { autofocus: false });
}

function renderCondraAiBox(content, emailText, subjectText, summary) {
  content.replaceChildren();
  content.dataset.condraStatus = summary === undefined ? "loading" : (summary ? "summary" : "no-summary");

  if (summary === undefined) {
    appendBoxLine(content, "Loading stored summary...", { color: "rgba(244,247,251,0.72)" });
    return;
  }

  appendCondraQuickActions(content, "summary");

  if (!summary) {
    appendBoxLine(content, "No stored summary found for this email yet.", { marginTop: "10px", color: "rgba(244,247,251,0.82)" });
    if (condraLastFetchInfo.error) {
      appendBoxLine(content, `Fetch issue: ${condraLastFetchInfo.error}`, { marginTop: "6px", color: "rgba(244,247,251,0.64)" });
    } else {
      appendBoxLine(content, `Checked account: ${condraLastFetchInfo.userEmail || "unknown"}`, { marginTop: "6px", color: "rgba(244,247,251,0.64)" });
      appendBoxLine(content, `Summaries loaded: ${condraLastFetchInfo.count}`, { color: "rgba(244,247,251,0.64)" });
    }
    appendCondraTerminalPrompt(content, { autofocus: false });
    return;
  }

  const bullets = Array.isArray(summary.bullets) ? summary.bullets : [];
  if (!bullets.length) {
    appendBoxLine(content, `Summary found: ${summary.subject || subjectText || "(No Subject)"}`, {
      marginTop: "10px",
      fontWeight: "700"
    });
    appendBoxLine(content, "No bullet points were parsed for this stored summary.", {
      marginTop: "7px",
      color: "rgba(244,247,251,0.72)"
    });
    if (summary.sender) {
      appendBoxLine(content, `From: ${summary.sender}`, {
        marginTop: "6px",
        color: "rgba(244,247,251,0.64)"
      });
    }
    appendObjectiveCompletionPreview(content, summary);
    appendCondraTerminalPrompt(content, { autofocus: false });
    return;
  }

  bullets.slice(0, 10).forEach((bullet, index) => {
    const section = document.createElement("div");
    section.className = "condra-summary-card";
    section.dataset.condraSummaryIndex = String(index);
    section.style.marginTop = index === 0 ? "10px" : "8px";
    section.style.padding = "10px 11px";
    section.style.borderRadius = "8px";
    section.style.transition = "background 160ms ease, outline 160ms ease";
    content.appendChild(section);

    if (bullet.point) {
      const point = appendBoxLine(section, `${index + 1}. ${bullet.point}`, {
        fontWeight: "600"
      });
      point.className = "condra-summary-point";
    }
    if (bullet.excerpt && normalizeForCondraMatch(bullet.excerpt) !== "no exact excerpt") {
      const excerpt = appendBoxLine(section, `Exact: ${bullet.excerpt}`, {
        marginTop: "7px",
        padding: "7px 9px",
        borderLeft: "3px solid #ffd86b",
        borderRadius: "8px"
      });
      excerpt.className = "condra-excerpt-line";
    }

  });

  appendObjectiveCompletionPreview(content, summary);

  appendCondraTerminalPrompt(content, { autofocus: false });
}

function isCondraActiveCommandSurface(content) {
  const status = content.dataset.condraStatus || "";
  if (status === "note-form" || status === "ask") return true;
  if (status === "no-email" && content.querySelector(".condra-terminal-row")) return true;
  return false;
}

function injectCondraHighlightStyles() {
  if (document.getElementById("condra-email-highlight-styles")) return;
  const style = document.createElement("style");
  style.id = "condra-email-highlight-styles";
  style.textContent = `
    .condra-email-highlight {
      color: #111 !important;
      padding: 1px 2px !important;
      border-radius: 2px !important;
      box-decoration-break: clone !important;
      -webkit-box-decoration-break: clone !important;
    }
  `;
  document.documentElement.appendChild(style);
}

function cleanCondraDomText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function isBadOutlookSubject(value) {
  const text = cleanCondraDomText(value).toLowerCase();
  if (!text) return true;
  if (text.length > 240) return true;
  return [
    "mail",
    "outlook",
    "inbox",
    "sent items",
    "deleted items",
    "junk email",
    "archive",
    "focused",
    "other"
  ].includes(text);
}

function getOutlookMessageIdFromLocation() {
  const candidates = [];
  try {
    const url = new URL(location.href);
    ["itemid", "ItemID", "id", "messageId"].forEach((key) => {
      const value = url.searchParams.get(key);
      if (value) candidates.push(value);
    });
    const hashText = decodeURIComponent(String(url.hash || ""));
    const hashParamsText = hashText.includes("?") ? hashText.slice(hashText.indexOf("?") + 1) : hashText.replace(/^#/, "");
    const hashParams = new URLSearchParams(hashParamsText);
    ["itemid", "ItemID", "id", "messageId"].forEach((key) => {
      const value = hashParams.get(key);
      if (value) candidates.push(value);
    });
    const itemMatch = hashText.match(/(?:itemid|ItemID|messageId|id)[=/]([^&/#?]+)/);
    if (itemMatch) candidates.push(itemMatch[1]);
    const pathMatch = `${url.pathname}${hashText}`.match(/\/(?:id|item|messages?)\/([^/?#&]+)/i);
    if (pathMatch) candidates.push(pathMatch[1]);
    const encodedIdMatch = `${url.pathname}${hashText}`.match(/A[A-Za-z0-9%_-]{40,}/);
    if (encodedIdMatch) candidates.push(encodedIdMatch[0]);
  } catch (err) {
    // ignore
  }
  return cleanCondraDomText(candidates.find(Boolean) || "");
}

function getOutlookMainScope() {
  return document.querySelector('div[role="main"]') || document.body;
}

function isOutlookMessageCandidate(el) {
  if (!el || !isVisible(el) || el.closest("#black-box")) return false;
  if (el.closest('[role="navigation"], nav, aside, [role="grid"], [aria-label*="Message list"], [aria-label*="Folder"]')) return false;
  const text = cleanCondraDomText(el.innerText || el.textContent || "");
  return text.length >= 12;
}

function getOutlookBodyRoot() {
  const candidates = getOutlookBodyRootCandidates();
  return candidates.length ? candidates[0] : null;
}

function getOutlookBodyRootCandidates() {
  const main = getOutlookMainScope();
  const selectors = [
    '[aria-label="Message body"]',
    '[aria-label*="Message body"]',
    '[data-app-section="MessageBody"]',
    '[data-testid*="messageBody"]',
    '[data-testid*="MessageBody"]',
    'div[role="document"]',
    'article',
    'div[dir="ltr"]'
  ].join(",");
  const candidates = Array.from(main.querySelectorAll(selectors))
    .filter(isOutlookMessageCandidate)
    .map((el) => ({ el, text: cleanCondraDomText(el.innerText || el.textContent || "") }))
    .filter((item) => !isBadOutlookSubject(item.text));
  candidates.sort((a, b) => b.text.length - a.text.length);
  const roots = candidates.map((item) => item.el);
  if (isOutlookMessageCandidate(main)) roots.push(main);
  roots.push(document.body);
  return [...new Set(roots)].filter(Boolean);
}

function getOutlookSubject(bodyRoot) {
  const main = getOutlookMainScope();
  const containers = [];
  let cur = bodyRoot;
  while (cur && cur !== document.body && containers.length < 5) {
    containers.push(cur);
    cur = cur.parentElement;
  }
  containers.push(main);

  const selectors = [
    '[data-testid*="message-subject"]',
    '[data-testid*="MessageSubject"]',
    '[aria-label^="Subject"]',
    'h1',
    'h2',
    'div[role="heading"][aria-level="1"]',
    'div[role="heading"][aria-level="2"]'
  ];

  for (const container of containers) {
    for (const sel of selectors) {
      for (const el of Array.from(container.querySelectorAll(sel))) {
        if (!isVisible(el)) continue;
        let text = cleanCondraDomText(el.getAttribute("aria-label") || el.textContent || "");
        text = text.replace(/^subject\s*[:\-]\s*/i, "");
        if (!isBadOutlookSubject(text)) return { text, el };
      }
    }
  }

  const titleSubject = cleanCondraDomText(document.title).split(" - ")[0];
  if (!isBadOutlookSubject(titleSubject)) return { text: titleSubject, el: null };
  return null;
}

function getOutlookSender(bodyRoot) {
  const main = getOutlookMainScope();
  const containers = [];
  let cur = bodyRoot;
  while (cur && cur !== document.body && containers.length < 5) {
    containers.push(cur);
    cur = cur.parentElement;
  }
  containers.push(main);

  for (const container of containers) {
    const mailto = container.querySelector('a[href^="mailto:"]');
    if (mailto) {
      const email = extractEmailFromString(mailto.getAttribute("href") || mailto.textContent || "");
      if (email) return { text: email, el: mailto };
    }
    const attrEls = Array.from(container.querySelectorAll('[aria-label*="@"], [title*="@"]')).filter(isVisible);
    for (const el of attrEls) {
      const email = extractEmailFromString(el.getAttribute("aria-label") || el.getAttribute("title") || el.textContent || "");
      if (email) return { text: email, el };
    }
  }
  return null;
}

function getOpenMessageBodyRoot() {
  const main = document.querySelector('div[role="main"]');
  if (!main) return null;

  if (isCondraOutlookHost()) {
    return getOutlookBodyRoot();
  }

  const bodySelectors = isCondraOutlookHost()
    ? [
        'div[aria-label="Message body"]',
        'div[role="document"]',
        '[data-app-section="MessageBody"]',
        '[data-testid*="messageBody"]',
        '[data-testid*="MessageBody"]',
        'div[dir="ltr"]'
      ].join(",")
    : "div.a3s, div[role='listitem'] div[dir='ltr']";

  const bodies = Array.from(main.querySelectorAll(bodySelectors))
    .filter((el) => isVisible(el) && !el.closest("#black-box"));
  return bodies.length ? bodies[bodies.length - 1] : null;
}

function clearCondraEmailHighlights(root) {
  const scope = root || document;
  scope.querySelectorAll("span.condra-email-highlight").forEach((span) => {
    const parent = span.parentNode;
    if (!parent) return;
    while (span.firstChild) parent.insertBefore(span.firstChild, span);
    parent.removeChild(span);
    parent.normalize();
  });
}

function collectCondraTextEntries(root) {
  const entries = [];
  let fullText = "";
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      const parent = node.parentElement;
      if (!parent) return NodeFilter.FILTER_REJECT;
      if (parent.closest("#black-box, script, style, span.condra-email-highlight")) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }
  });

  while (walker.nextNode()) {
    const node = walker.currentNode;
    const start = fullText.length;
    fullText += node.nodeValue;
    entries.push({ node, start, end: fullText.length });
  }

  return { entries, fullText };
}

function applyCondraHighlightRange(entries, start, end, color, summaryIndex) {
  if (start < 0 || end <= start) return false;
  let applied = false;

  for (const entry of entries) {
    let node = entry.node;
    if (!node.parentNode) continue;
    if (entry.end <= start || entry.start >= end) continue;

    const localStart = Math.max(0, start - entry.start);
    const localEnd = Math.min(entry.end - entry.start, end - entry.start);
    if (localEnd <= localStart) continue;

    if (localStart > 0) node = node.splitText(localStart);
    if (localEnd - localStart < node.nodeValue.length) node.splitText(localEnd - localStart);

    const span = document.createElement("span");
    span.className = "condra-email-highlight";
    span.style.backgroundColor = color;
    span.style.cursor = "pointer";
    span.title = "Show matching AI summary";
    span.dataset.condraSummaryIndex = String(summaryIndex);
    span.textContent = node.nodeValue;
    span.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      selectCondraSummaryIndex(summaryIndex);
    });
    node.parentNode.replaceChild(span, node);
    applied = true;
  }

  return applied;
}

function findCondraHighlightMatch(fullText, text) {
  const tokens = (normalizeForCondraMatch(text).match(/[\p{L}\p{N}\p{M}]+/gu) || []).filter(Boolean);
  if (!tokens.length) return null;

  const pattern = new RegExp(tokens.map(escapeRegExp).join("[^\\p{L}\\p{N}\\p{M}]+"), "iu");
  const match = fullText.match(pattern);
  if (match && match.index != null && match[0].length >= 6) {
    return { start: match.index, end: match.index + match[0].length };
  }
  return null;
}

function condraHighlightFallbackTexts(bullet) {
  const texts = [];
  const excerpt = String((bullet && bullet.excerpt) || "").trim();
  const point = String((bullet && bullet.point) || "").trim();
  if (excerpt && normalizeForCondraMatch(excerpt) !== "no exact excerpt") texts.push(excerpt);

  const pointWords = point.split(/\s+/).filter((word) => word.length > 2);
  for (let size = Math.min(12, pointWords.length); size >= 4; size -= 1) {
    texts.push(pointWords.slice(0, size).join(" "));
  }
  return [...new Set(texts.map((text) => text.trim()).filter(Boolean))];
}

function condraStoredBodyFallbackTexts(summary) {
  const body = cleanCondraDomText(String((summary && summary.bodyText) || ""));
  if (!body) return [];
  const sentenceLike = body
    .split(/(?<=[.!?])\s+|\n+/)
    .map((text) => cleanCondraDomText(text))
    .filter((text) => text.length >= 12 && text.length <= 260);
  const chunks = [];
  if (body.length >= 12) chunks.push(body.slice(0, 220));
  sentenceLike.slice(0, 8).forEach((text) => chunks.push(text));
  return [...new Set(chunks)];
}

function applyCondraFallbackBodyHighlights(roots, summary, colors) {
  const texts = condraStoredBodyFallbackTexts(summary).slice(0, 5);
  if (!texts.length) return { applied: 0, usedRoot: roots[0] || null };

  for (const candidateRoot of roots) {
    let count = 0;
    clearCondraEmailHighlights(document);
    for (const text of texts) {
      const snapshot = collectCondraTextEntries(candidateRoot);
      const found = findCondraHighlightMatch(snapshot.fullText, text);
      if (!found) continue;
      if (applyCondraHighlightRange(snapshot.entries, found.start, found.end, colors[count % colors.length], count)) {
        count += 1;
      }
      if (count >= 3) break;
    }
    if (count > 0) return { applied: count, usedRoot: candidateRoot };
  }
  return { applied: 0, usedRoot: roots[0] || null };
}

function highlightCondraExcerptsInEmail(summary) {
  if (condraApplyingHighlights) return;

  const roots = isCondraOutlookHost()
    ? getOutlookBodyRootCandidates()
    : [getOpenMessageBodyRoot()].filter(Boolean);
  const root = roots[0] || null;
  if (!root) {
    clearCondraEmailHighlights(document);
    return { applied: 0, rootFound: false, bullets: Array.isArray(summary && summary.bullets) ? summary.bullets.length : 0 };
  }

  condraApplyingHighlights = true;
  let appliedCount = 0;
  try {
    injectCondraHighlightStyles();
    clearCondraEmailHighlights(document);

    if (!summary || !Array.isArray(summary.bullets)) {
      return { applied: 0, rootFound: true, rootTextLength: cleanCondraDomText(root.innerText || root.textContent || "").length, bullets: 0 };
    }

    const colors = ["#FFD700", "#FF6B6B", "#4ECDC4", "#95E1D3", "#F38181", "#AA96DA", "#FCBAD3", "#A8D8EA", "#FFB6B9", "#8FD14F"];
    const excerpts = summary.bullets
      .map((bullet, index) => ({ texts: condraHighlightFallbackTexts(bullet), summaryIndex: index }))
      .filter((item) => item.texts.length)
      .slice(0, 10);

    let usedRoot = root;
    for (const candidateRoot of roots) {
      clearCondraEmailHighlights(document);
      appliedCount = 0;
      excerpts.forEach((item, index) => {
        const snapshot = collectCondraTextEntries(candidateRoot);
        let found = null;
        for (const text of item.texts) {
          found = findCondraHighlightMatch(snapshot.fullText, text);
          if (found) break;
        }
        if (!found) return;

        const applied = applyCondraHighlightRange(
          snapshot.entries,
          found.start,
          found.end,
          colors[index % colors.length],
          item.summaryIndex
        );
        if (applied) appliedCount += 1;
      });
      if (appliedCount > 0) {
        usedRoot = candidateRoot;
        break;
      }
    }
    if (appliedCount <= 0) {
      const fallback = applyCondraFallbackBodyHighlights(roots, summary, colors);
      appliedCount = fallback.applied;
      usedRoot = fallback.usedRoot || usedRoot;
    }
    return {
      applied: appliedCount,
      rootFound: true,
      rootCount: roots.length,
      rootTextLength: cleanCondraDomText(usedRoot.innerText || usedRoot.textContent || "").length,
      bullets: summary.bullets.length,
      candidates: excerpts.length
    };
  } finally {
    condraApplyingHighlights = false;
  }
}

async function updateCondraAiBox(emailText, subjectText, snippetText = "", timeText = "", messageId = "") {
  const content = document.getElementById('black-box-content');
  if (!content) return;

  const key = `${emailText || ""}|${subjectText || ""}|${String(snippetText || "").slice(0, 500)}|${timeText || ""}`;
  if (content.dataset.condraKey === key && content.dataset.condraStatus && content.dataset.condraStatus !== "loading") {
    if (condraCurrentSummary) highlightCondraExcerptsInEmail(condraCurrentSummary);
    return;
  }

  const requestId = ++condraAiBoxRequestId;
  content.dataset.condraKey = key;
  condraCurrentSummary = null;
  condraCurrentEmailText = emailText || "";
  condraCurrentSubjectText = subjectText || "";
  renderCondraAiBox(content, emailText, subjectText, undefined);

  const match = await fetchCondraSummaryLikeSuperTest(subjectText, snippetText, timeText, messageId);
  if (requestId !== condraAiBoxRequestId) return;

  condraCurrentSummary = match;
  condraCurrentEmailText = emailText || "";
  condraCurrentSubjectText = subjectText || "";
  if (match && typeof window.condraOpenPanel === "function") window.condraOpenPanel();
  renderCondraAiBox(content, emailText, subjectText, match);
  highlightCondraExcerptsInEmail(match);
}

function updateBlackBoxText() {
  console.debug('content.js: updateBlackBoxText called, url=', location.href);
  const box = document.getElementById('black-box');
  const content = document.getElementById('black-box-content');
  if (!box || !content) return;
  if (isCondraMailHost()) {
    // If a message is open, prefer the sender of the open message (only if visible)
    const openMsgEmailObj = getOpenMessageEmail();
    const openMsgSubjectObj = getOpenMessageSubject();
    console.debug('content.js: open message detection', {openMsgEmailObj, openMsgSubjectObj});
    const emailText = openMsgEmailObj && openMsgEmailObj.text;
    const subjText = openMsgSubjectObj && openMsgSubjectObj.text;
    const emailEl = openMsgEmailObj && openMsgEmailObj.el;
    const subjEl = openMsgSubjectObj && openMsgSubjectObj.el;
    const bodyRoot = getOpenMessageBodyRoot();
    const snippetText = bodyRoot ? bodyRoot.innerText.trim() : "";
    const timeText = getOpenMessageTime();
    const messageId = isCondraOutlookHost() ? getOutlookMessageIdFromLocation() : "";

    const showOpen = (emailText && (!emailEl || isVisible(emailEl))) || (subjText && (!subjEl || isVisible(subjEl))) || !!snippetText;
    if (showOpen) {
      updateCondraAiBox(
        emailText && (!emailEl || isVisible(emailEl)) ? emailText : "",
        subjText && (!subjEl || isVisible(subjEl)) ? subjText : "",
        snippetText,
        timeText,
        messageId
      );
      return;
    }

    // When not viewing an open message, show a clear indicator instead of account email
    clearCondraEmailHighlights(document);
    condraCurrentSummary = null;
    condraCurrentEmailText = "";
    condraCurrentSubjectText = "";
    content.dataset.condraKey = "";
    if (!isCondraActiveCommandSurface(content)) {
      renderCondraTerminalBox(content, "Not viewing an email. Commands still work.");
    }
  } else {
    clearCondraEmailHighlights(document);
    condraCurrentSummary = null;
    condraCurrentEmailText = "";
    condraCurrentSubjectText = "";
    content.dataset.condraKey = "";
    if (!isCondraActiveCommandSurface(content)) {
      renderCondraTerminalBox(content, "Commands still work here.");
    }
  }
}

function getOpenMessageSubject() {
  try {
    if (isCondraOutlookHost()) {
      const subject = getOutlookSubject(getOpenMessageBodyRoot());
      if (subject) return subject;
    }

    const main = document.querySelector('div[role="main"]');
    if (!main) {
      console.debug('content.js: getOpenMessageSubject no main');
      return null;
    }

    // Common Gmail subject selectors
    const selectors = [
      'h2.hP',
      'h1.hP',
      'h2[data-legacy-subject]',
      'h2[role="heading"]',
      'div.if > h2',
      'h1',
      'div[role="heading"][aria-level="1"]',
      '[data-testid*="message-subject"]',
      '[data-testid*="MessageSubject"]',
      '[aria-label^="Subject"]'
    ];
    for (const sel of selectors) {
      const el = main.querySelector(sel);
      if (el && el.textContent) {
        const s = el.textContent.trim();
        console.debug('content.js: getOpenMessageSubject candidate', sel, s);
        if (s) return { text: s, el };
      }
    }

    // Fallback: any element in the message header that looks like a subject (short text)
    const header = main.querySelector('table, div.a3s, div.adn, header, div[role="heading"]');
    if (header) {
      const headings = header.querySelectorAll('h1,h2,h3,span');
      for (const h of headings) {
        const t = h.textContent.trim();
        if (t && t.length > 2 && t.length < 200 && /\w/.test(t)) return { text: t, el: h };
      }
    }
  } catch (err) {
    console.debug('content.js: getOpenMessageSubject error', err);
  }
  return null;
}

function getOpenMessageTime() {
  try {
    const main = document.querySelector('div[role="main"]');
    if (!main) return "";
    const selectors = [
      "span.g3",
      "td.gH span[title]",
      "span[title][alt]",
      "[data-testid*='SentReceivedSavedTime']",
      "[aria-label*='Sent']",
      "[aria-label*='Received']",
      "span[title]"
    ];
    for (const sel of selectors) {
      const el = main.querySelector(sel);
      if (!el || !isVisible(el)) continue;
      const value = el.getAttribute("title") || el.getAttribute("alt") || el.textContent || "";
      const clean = String(value || "").trim();
      if (clean) return clean;
    }
  } catch (err) {
    console.debug("content.js: getOpenMessageTime error", err);
  }
  return "";
}

function getOpenMessageEmail() {
  try {
    if (isCondraOutlookHost()) {
      const sender = getOutlookSender(getOpenMessageBodyRoot());
      if (sender) return sender;
    }

    const main = document.querySelector('div[role="main"]');
    if (!main) {
      console.debug('content.js: getOpenMessageEmail no main');
      return null;
    }
    // Prefer targeted selectors commonly used by Gmail for the sender
    const selectors = [
      'span[email]',
      'span.gD',
      'span.gB',
      '[data-hovercard-id]',
      'a[href^="mailto:"]',
      '[aria-label*="@"]',
      '[title*="@"]',
      'h3 span'
    ];
    for (const sel of selectors) {
      const el = main.querySelector(sel);
      if (el) {
        const attr = el.getAttribute('email') || el.getAttribute('data-hovercard-id') || el.getAttribute('href') || el.getAttribute('aria-label') || el.alt || el.title || el.textContent;
        const e = extractEmailFromString(attr);
        console.debug('content.js: getOpenMessageEmail candidate', sel, '->', e);
        if (e) return { text: e, el };
      }
    }
  } catch (err) {
    console.debug('content.js: getOpenMessageEmail error', err);
  }
  return null;
}

// Debounce helper to limit updates
function debounce(fn, wait) {
  let t = null;
  return function(...args) {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), wait);
  };
}

const debouncedUpdate = debounce(updateBlackBoxText, 300);

// Watch for DOM changes but avoid expensive full-document scans — only react to likely relevant changes
const observer = new MutationObserver((mutations) => {
  for (const m of mutations) {
    if (m.type === 'childList') {
      for (const node of m.addedNodes) {
        if (!(node instanceof HTMLElement)) continue;
        if (node.classList.contains("condra-email-highlight") || node.closest(".condra-email-highlight")) continue;
        if (node.closest && (node.closest('div[role="main"]') || node.closest('header') || node.querySelector && node.querySelector('[email], [data-hovercard-id], img[alt*="@"], a[href^="mailto:"]')) ) {
          debouncedUpdate();
          return;
        }
      }
    } else if (m.type === 'attributes') {
      const name = m.attributeName;
      if (name && (name === 'aria-label' || name === 'alt' || name === 'title' || name === 'email' || name === 'data-hovercard-id')) {
        debouncedUpdate();
        return;
      }
    }
  }
});

let isObserving = false;
function startObserverIfGmail() {
  try {
    if (isCondraMailHost()) {
      if (!isObserving) {
        observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['aria-label','alt','title','email','data-hovercard-id'] });
        isObserving = true;
        console.debug('content.js: observer started');
      }
    } else {
      if (isObserving) {
        observer.disconnect();
        isObserving = false;
        console.debug('content.js: observer stopped');
      }
    }
  } catch (err) {
    console.debug('content.js: startObserverIfGmail error', err);
  }
}
(function() {
  const pushState = history.pushState;
  history.pushState = function() {
    pushState.apply(this, arguments);
    window.dispatchEvent(new Event('locationchange'));
  };
  const replaceState = history.replaceState;
  history.replaceState = function() {
    replaceState.apply(this, arguments);
    window.dispatchEvent(new Event('locationchange'));
  };
})();

const condraExtensionApi = typeof browser !== "undefined" ? browser : (typeof chrome !== "undefined" ? chrome : null);
if (condraExtensionApi && condraExtensionApi.runtime && condraExtensionApi.runtime.onMessage) {
  condraExtensionApi.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (!message) return false;

    if (message.type === "CONDRA_HIGHLIGHT_SUMMARY") {
      const summary = message.summary || null;
      const first = highlightCondraExcerptsInEmail(summary) || {};
      window.setTimeout(() => highlightCondraExcerptsInEmail(summary), 150);
      window.setTimeout(() => highlightCondraExcerptsInEmail(summary), 600);
      window.setTimeout(() => highlightCondraExcerptsInEmail(summary), 1400);
      sendResponse({ ok: true, highlight: first });
      return false;
    }

    if (message.type === "CONDRA_FOCUS_HIGHLIGHT") {
      const index = Number(message.index || 0);
      const focused = focusCondraEmailHighlight(index);
      if (!focused) {
        window.setTimeout(() => focusCondraEmailHighlight(index), 500);
      }
      sendResponse({ ok: true, focused });
      return false;
    }

    if (message.type !== "CONDRA_GET_OPEN_EMAIL") return false;

    const emailObj = getOpenMessageEmail();
    const subjectObj = getOpenMessageSubject();
    const bodyRoot = getOpenMessageBodyRoot();
    sendResponse({
      id: isCondraOutlookHost() ? getOutlookMessageIdFromLocation() : "",
      userEmail: getGmailEmail() || "",
      provider: isCondraOutlookHost() ? "outlook" : "gmail",
      url: location.href,
      sender: emailObj && emailObj.text || "",
      subject: subjectObj && subjectObj.text || "",
      snippet: bodyRoot ? bodyRoot.innerText.trim() : "",
      time: getOpenMessageTime(),
      isOpen: !!(emailObj || subjectObj || bodyRoot)
    });
    return false;
  });
}

window.addEventListener("locationchange", () => {
  startObserverIfGmail();
  window.setTimeout(updateBlackBoxText, 250);
});
window.addEventListener("popstate", () => {
  startObserverIfGmail();
  window.setTimeout(updateBlackBoxText, 250);
});
window.addEventListener("load", () => {
  startObserverIfGmail();
  window.setTimeout(updateBlackBoxText, 500);
});
startObserverIfGmail();
window.setTimeout(updateBlackBoxText, 800);
