/* Waypoint UI — PREMIUM WOW LAYER
   Sophisticated cursor + scroll interactions for Apple/OpenAI-level response.
   Vanilla JS, 60fps optimized, no dependencies. Fully additive to existing wow.js
   ========================================================================== */

(function () {
  const isMobile = () => window.innerWidth < 768;
  const isTablet = () => window.innerWidth < 1024;
  
  /* ========== SCROLL-LINKED ANIMATION ENGINE ========== */
  class ScrollLinkedAnimator {
    constructor() {
      this.triggers = [];
      this.scrollProgress = 0;
      this.lastScrollY = 0;
      this.ticking = false;
      this.init();
    }

    init() {
      window.addEventListener('scroll', () => this.onScroll(), { passive: true });
      this.onScroll();
    }

    onScroll() {
      if (this.ticking) return;
      this.ticking = true;
      requestAnimationFrame(() => this.updateAnimations());
    }

    updateAnimations() {
      const scrollY = window.scrollY;
      const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
      this.scrollProgress = maxScroll > 0 ? scrollY / maxScroll : 0;
      this.lastScrollY = scrollY;

      this.triggers.forEach(trigger => trigger.update(scrollY));
      this.ticking = false;
    }

    register(trigger) {
      this.triggers.push(trigger);
    }

    static createSectionReveal(selector, options = {}) {
      const opts = {
        scale: options.scale !== undefined ? options.scale : 0.92,
        opacity: options.opacity !== undefined ? options.opacity : 0.6,
        translateY: options.translateY !== undefined ? options.translateY : 30,
        ...options
      };

      return new ScrollLinkedTrigger(selector, (el, progress) => {
        const rect = el.getBoundingClientRect();
        const triggerTop = rect.top / window.innerHeight;
        
        if (triggerTop > 1) return; // below viewport
        if (triggerTop < -1.2) return; // far above viewport

        // Map trigger position to animation progress
        const localProgress = Math.max(0, Math.min(1, 1 - triggerTop - 0.1));
        
        // Smooth easing
        const eased = localProgress < 0.5 
          ? 2 * localProgress * localProgress 
          : -1 + (4 - 2 * localProgress) * localProgress;

        const scale = opts.scale + (1 - opts.scale) * eased;
        const opacity = opts.opacity + (1 - opts.opacity) * eased;
        const translateY = opts.translateY * (1 - eased);

        el.style.transform = `scale(${scale}) translateY(${translateY}px)`;
        el.style.opacity = opacity;
      });
    }

    static createParallax(selector, strength = 0.5) {
      return new ScrollLinkedTrigger(selector, (el, progress) => {
        const rect = el.getBoundingClientRect();
        const scrollY = window.scrollY;
        const offset = (scrollY - (el.offsetTop - window.innerHeight)) * strength;
        el.style.transform = `translateY(${offset}px)`;
      });
    }
  }

  class ScrollLinkedTrigger {
    constructor(selector, updateFn) {
      this.elements = document.querySelectorAll(selector);
      this.updateFn = updateFn;
      this.lastScrollY = 0;
    }

    update(scrollY) {
      const progress = scrollY / Math.max(document.documentElement.scrollHeight - window.innerHeight, 1);
      this.elements.forEach(el => {
        try {
          this.updateFn(el, progress);
        } catch (e) {
          console.warn('Scroll animation error:', e);
        }
      });
    }
  }

  /* ========== CURSOR TRACKING ENGINE ========== */
  class CursorTracker {
    constructor() {
      this.x = 0;
      this.y = 0;
      this.vx = 0; // velocity x
      this.vy = 0; // velocity y
      this.lastX = 0;
      this.lastY = 0;
      this.elements = [];
      this.enabled = !isMobile(); // disable on mobile
      
      if (this.enabled) {
        this.init();
      }
    }

    init() {
      document.addEventListener('mousemove', (e) => this.onMouseMove(e), { passive: true });
      document.addEventListener('mouseenter', () => this.onMouseEnter(), { passive: true });
      document.addEventListener('mouseleave', () => this.onMouseLeave(), { passive: true });
    }

    onMouseMove(e) {
      this.lastX = this.x;
      this.lastY = this.y;
      this.x = e.clientX;
      this.y = e.clientY;
      this.vx = this.x - this.lastX;
      this.vy = this.y - this.lastY;
      
      this.updateTrackedElements();
    }

    onMouseEnter() {
      this.elements.forEach(el => {
        if (el.onCursorEnter) el.onCursorEnter();
      });
    }

    onMouseLeave() {
      this.elements.forEach(el => {
        if (el.onCursorLeave) el.onCursorLeave();
      });
    }

    updateTrackedElements() {
      this.elements.forEach(el => {
        if (el.updateCursor) el.updateCursor(this.x, this.y, this.vx, this.vy);
      });
    }

    register(element) {
      this.elements.push(element);
    }

    static createProximityEffect(selector, options = {}) {
      const opts = {
        radius: options.radius || 150,
        maxScale: options.maxScale || 1.05,
        maxGlow: options.maxGlow || 0.3,
        ...options
      };

      return class ProximityElement {
        constructor(el) {
          this.el = el;
          this.rect = el.getBoundingClientRect();
          this.baseOpacity = parseFloat(window.getComputedStyle(el).opacity) || 1;
          this.baseScale = 1;
        }

        updateCursor(cursorX, cursorY, vx, vy) {
          this.rect = this.el.getBoundingClientRect();
          const centerX = this.rect.left + this.rect.width / 2;
          const centerY = this.rect.top + this.rect.height / 2;
          
          const dx = cursorX - centerX;
          const dy = cursorY - centerY;
          const distance = Math.sqrt(dx * dx + dy * dy);
          
          if (distance < opts.radius) {
            const proximity = 1 - (distance / opts.radius);
            const scale = this.baseScale + (opts.maxScale - this.baseScale) * proximity;
            const opacity = this.baseOpacity + (1 - this.baseOpacity) * proximity * 0.5;
            
            this.el.style.transform = `scale(${scale})`;
            this.el.style.opacity = opacity;
          } else {
            this.el.style.transform = '';
            this.el.style.opacity = this.baseOpacity;
          }
        }

        onCursorLeave() {
          this.el.style.transform = '';
          this.el.style.opacity = this.baseOpacity;
        }
      };
    }
  }

  /* ========== ROUTE VISUALIZATION ENGINE ========== */
  class RouteVisualizer {
    static createRouteTransition(routeSelector, options = {}) {
      const opts = {
        duration: options.duration || 1200,
        staggerDelay: options.staggerDelay || 40,
        ...options
      };

      return new ScrollLinkedTrigger(routeSelector, (el, progress) => {
        const rect = el.getBoundingClientRect();
        const triggerTop = rect.top / window.innerHeight;
        
        if (triggerTop > 1.2 || triggerTop < -0.8) return;

        // Scroll-triggered route animation
        const localProgress = Math.max(0, Math.min(1, 0.7 - triggerTop));
        
        // Scale path progressively
        el.style.transform = `scaleX(${localProgress}) scaleY(${0.6 + localProgress * 0.4})`;
        el.style.opacity = 0.3 + localProgress * 0.7;
        
        // Reveal vehicle/metadata on scroll
        const metadata = el.querySelector('[data-route-meta]');
        if (metadata) {
          const metaProgress = Math.max(0, Math.min(1, 2 * (localProgress - 0.3)));
          metadata.style.opacity = metaProgress;
          metadata.style.transform = `translateY(${(1 - metaProgress) * 8}px)`;
        }
      });
    }

    static createVehicleGlide(vehicleSelector, options = {}) {
      const opts = {
        speed: options.speed || 0.3,
        ...options
      };

      const elements = document.querySelectorAll(vehicleSelector);
      elements.forEach(el => {
        el.dataset.startX = el.offsetLeft;
        el.dataset.startProgress = 0;
      });

      return new ScrollLinkedTrigger(vehicleSelector, (el, progress) => {
        const startX = parseFloat(el.dataset.startX) || 0;
        const route = el.closest('[data-route]');
        
        if (route) {
          const routeRect = route.getBoundingClientRect();
          const routeProgress = Math.max(0, Math.min(1, 0.8 - routeRect.top / window.innerHeight));
          
          const moveDistance = routeRect.width * routeProgress * opts.speed;
          el.style.transform = `translateX(${moveDistance}px) scale(${0.8 + routeProgress * 0.2})`;
          el.style.opacity = 0.5 + routeProgress * 0.5;
        }
      });
    }
  }

  /* ========== ELEMENT RESPONSE ENGINE ========== */
  class ElementResponder {
    static createCursorDirectionResponse(selector, options = {}) {
      const opts = {
        strength: options.strength || 0.12,
        distance: options.distance || 3,
        ...options
      };

      const elements = document.querySelectorAll(selector);
      
      const tracker = {
        updateCursor(cursorX, cursorY, vx, vy) {
          elements.forEach(el => {
            if (!el.dataset.baseTransform) {
              el.dataset.baseTransform = el.style.transform || '';
            }
            
            const rect = el.getBoundingClientRect();
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;
            
            const dx = cursorX - centerX;
            const dy = cursorY - centerY;
            const distance = Math.sqrt(dx * dx + dy * dy);
            
            if (distance > 400) return;
            
            const angle = Math.atan2(dy, dx);
            const moveX = Math.cos(angle) * opts.distance * opts.strength;
            const moveY = Math.sin(angle) * opts.distance * opts.strength;
            
            const speed = Math.sqrt(vx * vx + vy * vy);
            const responsiveness = Math.min(1, speed / 15);
            
            el.style.transform = `translate(${moveX * responsiveness}px, ${moveY * responsiveness}px)`;
          });
        },

        onCursorLeave() {
          elements.forEach(el => {
            el.style.transform = el.dataset.baseTransform || '';
          });
        }
      };

      return tracker;
    }

    static createClickExpand(selector, options = {}) {
      const opts = {
        duration: options.duration || 400,
        expandScale: options.expandScale || 1.08,
        ...options
      };

      const elements = document.querySelectorAll(selector);
      elements.forEach(el => {
        el.addEventListener('click', (e) => {
          e.preventDefault();
          const start = performance.now();
          const baseTransform = el.style.transform;

          const animate = (now) => {
            const elapsed = now - start;
            const progress = Math.min(1, elapsed / opts.duration);
            
            // Ease in-out
            const eased = progress < 0.5 
              ? 2 * progress * progress 
              : -1 + (4 - 2 * progress) * progress;

            const scale = 1 + (opts.expandScale - 1) * eased;
            el.style.transform = `scale(${scale})`;

            if (progress < 1) {
              requestAnimationFrame(animate);
            } else {
              el.style.transform = baseTransform;
              // Navigate after animation
              const href = el.getAttribute('href');
              if (href) {
                setTimeout(() => {
                  window.location.href = href;
                }, 100);
              }
            }
          };

          requestAnimationFrame(animate);
        });
      });
    }
  }

  /* ========== STAGGERED SECTION REVEAL ========== */
  class SectionRevealController {
    static initForPage() {
      const sections = document.querySelectorAll('[data-wow-section]');
      sections.forEach((section, index) => {
        const items = section.querySelectorAll('[data-wow-item]');
        items.forEach((item, i) => {
          item.style.opacity = '0';
          item.style.transform = 'translateY(12px)';
          item.dataset.baseOpacity = '1';
          
          const delay = index * 100 + i * 35;
          setTimeout(() => {
            item.style.transition = `opacity 0.5s var(--ease), transform 0.5s var(--ease)`;
            item.style.opacity = item.dataset.baseOpacity;
            item.style.transform = 'translateY(0)';
          }, delay);
        });
      });
    }
  }

  /* ========== TOPBAR ANCHOR RESPONSE ========== */
  class TopbarAnchor {
    static createSticky() {
      const topbar = document.querySelector('.topbar');
      if (!topbar) return;

      let lastScrollY = 0;
      let isHiding = false;

      window.addEventListener('scroll', () => {
        const scrollY = window.scrollY;
        const delta = scrollY - lastScrollY;

        if (delta > 5 && !isHiding) {
          topbar.style.transform = 'translateY(-100%)';
          isHiding = true;
        } else if (delta < -5 && isHiding) {
          topbar.style.transform = 'translateY(0)';
          isHiding = false;
        }

        lastScrollY = scrollY;
      }, { passive: true });

      topbar.style.transition = 'transform 0.3s var(--ease)';
    }
  }

  /* ========== CARD ELEVATOR ========== */
  class CardElevator {
    static enhanceCards(selector, options = {}) {
      const opts = {
        baseElevation: options.baseElevation || 2,
        hoverElevation: options.hoverElevation || 12,
        ...options
      };

      const cards = document.querySelectorAll(selector);
      cards.forEach(card => {
        card.addEventListener('mouseenter', () => {
          card.style.transform = `translateY(-${opts.hoverElevation}px)`;
          card.style.boxShadow = `0 ${opts.hoverElevation * 2}px ${opts.hoverElevation * 3}px rgba(0,0,0,0.2)`;
        });
        
        card.addEventListener('mouseleave', () => {
          card.style.transform = `translateY(-${opts.baseElevation}px)`;
          card.style.boxShadow = `0 ${opts.baseElevation * 2}px ${opts.baseElevation * 3}px rgba(0,0,0,0.08)`;
        });
      });
    }
  }

  /* ========== SCROLL DAMPING (smoothing) ========== */
  class ScrollDamper {
    static smoothScroll() {
      if (isMobile()) return; // skip on mobile

      let currentScroll = 0;
      let targetScroll = 0;
      let isScrolling = false;

      window.addEventListener('scroll', () => {
        targetScroll = window.scrollY;
        if (!isScrolling) {
          isScrolling = true;
          requestAnimationFrame(() => this.updateScroll());
        }
      }, { passive: true });
    }

    static updateScroll() {
      const diff = targetScroll - currentScroll;
      if (Math.abs(diff) > 0.1) {
        currentScroll += diff * 0.2; // damping factor
        requestAnimationFrame(() => this.updateScroll());
      } else {
        currentScroll = targetScroll;
        isScrolling = false;
      }
    }
  }

  /* ========== RESPONSIVE CURSOR HANDLING ========== */
  class ResponsiveInteractions {
    static init() {
      if (isMobile()) {
        this.initMobileInteractions();
      } else if (isTablet()) {
        this.initTabletInteractions();
      } else {
        this.initDesktopInteractions();
      }

      window.addEventListener('resize', () => this.handleResize());
    }

    static initDesktopInteractions() {
      // Full cursor tracking + scroll
      const cursorTracker = new CursorTracker();
      const scrollAnimator = new ScrollLinkedAnimator();

      // Register proximity effects on cards
      document.querySelectorAll('.role-card').forEach(card => {
        const ProximityClass = CursorTracker.createProximityEffect('.role-card');
        const instance = new ProximityClass(card);
        cursorTracker.register(instance);
      });

      // Direction response
      const directionResponder = ElementResponder.createCursorDirectionResponse('[data-cursor-respond]');
      cursorTracker.register(directionResponder);

      // Route animations if present
      const routeTriggers = document.querySelectorAll('[data-route]');
      if (routeTriggers.length > 0) {
        routeTriggers.forEach(route => {
          scrollAnimator.register(
            RouteVisualizer.createRouteTransition(route)
          );
        });
      }
    }

    static initTabletInteractions() {
      // Simplified: scroll + touch only
      const scrollAnimator = new ScrollLinkedAnimator();
      document.querySelectorAll('[data-wow-section]').forEach(section => {
        scrollAnimator.register(
          ScrollLinkedAnimator.createSectionReveal(section)
        );
      });
    }

    static initMobileInteractions() {
      // Touch + scroll only, no cursor
      const scrollAnimator = new ScrollLinkedAnimator();
      document.querySelectorAll('[data-wow-section]').forEach(section => {
        scrollAnimator.register(
          ScrollLinkedAnimator.createSectionReveal(section)
        );
      });
    }

    static handleResize() {
      const wasDesktop = !isMobile() && !isTablet();
      const isNowDesktop = !isMobile() && !isTablet();
      
      if (wasDesktop !== isNowDesktop) {
        this.init();
      }
    }
  }

  /* ========== PUBLIC API ========== */
  window.WOWPremium = {
    ScrollLinkedAnimator,
    CursorTracker,
    RouteVisualizer,
    ElementResponder,
    SectionRevealController,
    TopbarAnchor,
    CardElevator,
    ScrollDamper,
    ResponsiveInteractions,
    
    // Convenience methods
    initPage() {
      ResponsiveInteractions.init();
      SectionRevealController.initForPage();
      ElementResponder.createClickExpand('.role-card');
      TopbarAnchor.createSticky();
    },

    initDispatcher() {
      ResponsiveInteractions.init();
      TopbarAnchor.createSticky();
      CardElevator.enhanceCards('.kpi-card');
      CardElevator.enhanceCards('.card');
    },

    initScrollAnimations(config = {}) {
      const animator = new ScrollLinkedAnimator();
      
      if (config.sectionReveal) {
        document.querySelectorAll('.section-hero, .section-feature').forEach(section => {
          animator.register(
            ScrollLinkedAnimator.createSectionReveal(section, config.sectionReveal)
          );
        });
      }

      if (config.parallax) {
        animator.register(
          ScrollLinkedAnimator.createParallax('[data-parallax]', config.parallax.strength || 0.4)
        );
      }

      return animator;
    }
  };
})();
