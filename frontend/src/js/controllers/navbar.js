import { Controller } from "@hotwired/stimulus";
import { gsap } from "gsap";

//! connects to data-controller="navbar"
// Mobile menu: hamburger button toggles a dropdown panel, links close it.
// Desktop nav (`md:` breakpoints) is plain CSS — no JS involved.
export default class extends Controller {
  static targets = ["mobileMenu", "hamburgerIcon", "closeIcon"];
  static animationDuration = 0.2; // seconds

  connect() {
    gsap.set(this.mobileMenuTarget, { autoAlpha: 0 });

    this.onKeydown = this.onKeydown.bind(this);
    this.onOutsideClick = this.onOutsideClick.bind(this);
    document.addEventListener("keydown", this.onKeydown);
    document.addEventListener("click", this.onOutsideClick);
  }

  disconnect() {
    document.removeEventListener("keydown", this.onKeydown);
    document.removeEventListener("click", this.onOutsideClick);
  }

  onKeydown(event) {
    if (event.key === "Escape" && !this.mobileMenuTarget.hidden) {
      this.closeMenu();
    }
  }

  onOutsideClick(event) {
    if (!this.mobileMenuTarget.hidden && !this.element.contains(event.target)) {
      this.closeMenu();
    }
  }

  toggleMenu() {
    if (this.mobileMenuTarget.hidden) {
      this.openMenu();
    } else {
      this.closeMenu();
    }
  }

  openMenu() {
    this.mobileMenuTarget.hidden = false;
    this.hamburgerIconTarget.hidden = true;
    this.closeIconTarget.hidden = false;
    this.setExpanded("true");

    gsap.to(this.mobileMenuTarget, {
      autoAlpha: 1,
      duration: this.constructor.animationDuration,
      ease: "power2.out",
    });
  }

  // Links in the menu carry data-action="click->navbar#closeMenu".
  closeMenu() {
    this.hamburgerIconTarget.hidden = false;
    this.closeIconTarget.hidden = true;
    this.setExpanded("false");

    gsap.to(this.mobileMenuTarget, {
      autoAlpha: 0,
      duration: this.constructor.animationDuration,
      ease: "power2.in",

      onComplete: () => {
        this.mobileMenuTarget.hidden = true;
      },
    });
  }

  // Mirror the state on both buttons so screen readers get it either way.
  setExpanded(value) {
    this.hamburgerIconTarget.setAttribute("aria-expanded", value);
    this.closeIconTarget.setAttribute("aria-expanded", value);
  }
}
