"use client";

import { useEffect, useRef } from "react";

/** How quickly the main glow catches up with the cursor (fraction of the gap closed per 60fps frame). */
const FOLLOW_EASE = 0.06;

/**
 * Page-wide living background: a fixed layer behind all content with one soft purple glow that
 * glides after the cursor (lerped in requestAnimationFrame) and two fainter glows drifting on
 * looping CSS paths. Only transform/opacity animate.
 *
 * - Touch / no hover: no cursor follow; the glows only drift.
 * - prefers-reduced-motion: static glow, no movement (CSS animations are switched off too).
 * - Hidden tab: the rAF loop stops and CSS drift is paused.
 */
export function BackgroundGlow() {
  const layerRef = useRef<HTMLDivElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const layer = layerRef.current;
    const glow = glowRef.current;
    if (!layer || !glow) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");

    // Resting spot: behind the hero, upper centre of the viewport.
    const home = () => ({ x: window.innerWidth * 0.5, y: Math.min(window.innerHeight * 0.22, 260) });
    const pos = home();
    let target = { ...pos };
    let following = false;
    let raf = 0;
    let last = 0;

    const apply = () => {
      glow.style.transform = `translate3d(${pos.x.toFixed(1)}px, ${pos.y.toFixed(1)}px, 0)`;
    };

    const tick = (now: number) => {
      const dt = last ? Math.min(now - last, 64) : 16.7;
      last = now;
      const k = 1 - Math.pow(1 - FOLLOW_EASE, dt / 16.7); // frame-rate independent lerp
      pos.x += (target.x - pos.x) * k;
      pos.y += (target.y - pos.y) * k;
      apply();
      if (Math.abs(target.x - pos.x) < 0.3 && Math.abs(target.y - pos.y) < 0.3) {
        raf = 0; // settled: stop the loop until the cursor moves again
        last = 0;
        return;
      }
      raf = requestAnimationFrame(tick);
    };

    const start = () => {
      if (!raf && !document.hidden && !reducedMotion.matches) raf = requestAnimationFrame(tick);
    };
    const stop = () => {
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
      last = 0;
    };

    const onPointerMove = (e: PointerEvent) => {
      if (e.pointerType !== "mouse" || !finePointer.matches || reducedMotion.matches) return;
      following = true;
      target = { x: e.clientX, y: e.clientY };
      start();
    };
    const onPointerLeave = () => {
      following = false;
      target = home();
      start();
    };
    const onResize = () => {
      if (following) return;
      target = home();
      if (reducedMotion.matches) {
        Object.assign(pos, target);
        apply();
      } else start();
    };
    const onVisibility = () => {
      layer.dataset.paused = String(document.hidden);
      if (document.hidden) stop();
      else start();
    };
    const onMotionChange = () => {
      if (reducedMotion.matches) {
        stop();
        following = false;
        Object.assign(pos, home());
        target = { ...pos };
        apply();
      }
    };

    apply();
    window.addEventListener("pointermove", onPointerMove, { passive: true });
    document.documentElement.addEventListener("pointerleave", onPointerLeave);
    window.addEventListener("resize", onResize, { passive: true });
    document.addEventListener("visibilitychange", onVisibility);
    reducedMotion.addEventListener("change", onMotionChange);

    return () => {
      stop();
      window.removeEventListener("pointermove", onPointerMove);
      document.documentElement.removeEventListener("pointerleave", onPointerLeave);
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVisibility);
      reducedMotion.removeEventListener("change", onMotionChange);
    };
  }, []);

  return (
    <div
      ref={layerRef}
      aria-hidden
      className="glow-layer pointer-events-none fixed inset-0 -z-20 overflow-hidden"
    >
      <div className="glow glow-drift-b" />
      <div className="glow glow-drift-a" />
      {/* Initial transform matches the resting spot so there is no jump on hydration. */}
      <div ref={glowRef} className="glow glow-main" style={{ transform: "translate3d(50vw, min(22vh, 260px), 0)" }}>
        <div className="glow-breathe" />
      </div>
    </div>
  );
}
