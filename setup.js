fetch('footer.html')
  .then((response) => response.text())
  .then((html) => {
    document.getElementById('footer-container').innerHTML = html
  })

fetch('menu.html')
  .then((response) => response.text())
  .then((html) => {
    const menuEl = document.getElementById('nav-container')
    const activePage = menuEl.getAttribute('data-active')
    menuEl.innerHTML = html
    if (activePage) {
      const activeMenuItem = menuEl.querySelector(`[data-page="${activePage}"]`)
      if (activeMenuItem) {
        activeMenuItem.parentElement.classList.add('selected-link')
      }
    }
    const script = document.createElement('script')
    script.src = 'menu.js'
    document.body.appendChild(script)
  })
