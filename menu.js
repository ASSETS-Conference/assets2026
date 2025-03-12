// https://www.w3.org/WAI/tutorials/menus/flyout/#use-button-as-toggle

var menuItems = document.querySelectorAll('li.has-submenu')

// Iterate through each menu item
Array.prototype.forEach.call(menuItems, function (el, i) {
  // Add an event listener for mouseover to add the 'open' class
  el.addEventListener('mouseover', function (event) {
    this.classList.add('open')
    // Clear any existing timeout when mouse enters
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }
  })

  // Add an event listener for mouseout to remove the 'open' class after 750ms
  el.addEventListener('mouseout', function (event) {
    this.timer = setTimeout(() => {
      this.classList.remove('open')
    }, 750)
  })

  // Add an event listener to the <a> element to toggle submenu visibility when clicked
  el.querySelector('a').addEventListener('click', function (event) {
    const parent = this.parentNode
    if (parent.classList.contains('open')) {
      // If submenu is already open, close it and update the aria-expanded attribute
      parent.classList.remove('open')
      this.setAttribute('aria-expanded', 'false')
    } else {
      // If submenu is closed, open it and update the aria-expanded attribute
      parent.classList.add('open')
      this.setAttribute('aria-expanded', 'true')
    }
  })

  // Insert a button to have a keyboard selectable toggle submenu after the <a> element for accessibility purposes
  let activatingA = el.querySelector('a')
  let btn = `<button class="submenu-toggle" aria-label="${activatingA.text}">
        <span>
          <span class="visually-hidden">show submenu for “${activatingA.text}”</span>
        </span>
      </button>`
  activatingA.insertAdjacentHTML('afterend', btn)

  // Add an event listener to the newly added button to toggle submenu
  el.querySelector('button').addEventListener('click', function (event) {
    if (this.parentNode.className == 'has-submenu') {
      // Open the submenu and update aria-expanded attributes
      this.parentNode.className = 'has-submenu open'
      this.parentNode.querySelector('a').setAttribute('aria-expanded', 'true')
      this.parentNode.querySelector('button').setAttribute('aria-expanded', 'true')
    } else {
      // Close the submenu and update aria-expanded attributes
      this.parentNode.className = 'has-submenu'
      this.parentNode.querySelector('a').setAttribute('aria-expanded', 'false')
      this.parentNode.querySelector('button').setAttribute('aria-expanded', 'false')
    }
    event.preventDefault() // Prevent default button action
  })
})

document.getElementById('menu-toggle').addEventListener('click', function () {
  const menuContainer = document.getElementById('menu-container')
  menuContainer.classList.toggle('open')
  this.classList.toggle('active')
  document.body.classList.toggle('menu-open')
  document.body.style.overflow = document.body.classList.contains('menu-open') ? 'hidden' : ''
})

// closes open submenus on escape key press
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') {
    document.querySelectorAll('.has-submenu.open').forEach(function (menu) {
      menu.classList.remove('open')
      const link = menu.querySelector('a')
      const toggle = menu.querySelector('.submenu-toggle')
      if (link) link.setAttribute('aria-expanded', 'false')
      if (toggle) toggle.setAttribute('aria-expanded', 'false')
    })
  }
})
