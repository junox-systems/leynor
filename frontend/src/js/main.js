// Import Vite modulepreload polyfill [django-vite docs]
import "vite/modulepreload-polyfill";

// import CSS styles
import "../css/styles.css";

// htmx 4 — boosted navigation for the authenticated app shell.
// Importing the package starts htmx for us.
import "htmx.org";

// Basecoat JS for the components we use (custom select, toasts). The core starts a
// MutationObserver, so components in htmx-swapped bodies init too.
import "basecoat-css/basecoat";
import "basecoat-css/select";
import "basecoat-css/toast";

// Opt-in, NOT global: only subtrees marked hx-boost:inherited="true" are
// boosted — i.e. the app shell in templates/base_app.html. Marketing pages keep
// plain page loads (their Three.js island is heavy and has its own lifecycle),
// and only the shell benefits from a persistent sidebar.
//
// Forms stay browser-native. hx-boost covers both links and forms; Django forms
// + full page loads are the primary pattern here, so refuse to boost a form
// that only inherited boost. A form with its own hx-post etc. is left alone.
document.addEventListener("htmx:before:init", (event) => {
  // htmx retargets events from detached elements to `document`, which has no
  // .matches — hence the instanceof guard.
  if (
    event.target instanceof HTMLFormElement &&
    !event.target.matches("[hx-action],[hx-get],[hx-post],[hx-put],[hx-patch],[hx-delete]")
  ) {
    event.preventDefault();
  }
});

// HyperDX — RUM, session replay, and frontend → backend trace linking. Opt-in.
//
// Imported DYNAMICALLY on purpose. It pulls in rrweb + OpenTelemetry (~650 kB),
// and VITE_HYPERDX_URL ships empty, so a static import made every page parse all
// of it and then never call it. `import.meta.env.VITE_*` is inlined at build
// time, so with the var unset this whole branch — and the chunk — is dropped.
//
// Consequence: enabling HyperDX requires a rebuild (already true, it is a
// build-time var), and init lands one microtask later, so the very earliest
// console/network events are not captured.
const hyperdxUrl = import.meta.env.VITE_HYPERDX_URL;
if (hyperdxUrl) {
  const initConfig = {
    service:
      import.meta.env.VITE_HYPERDX_SERVICE || "frontend",
    url: hyperdxUrl,
    consoleCapture: true,
    tracePropagationTargets: [/\/api\/v1\//i],
    otelResourceAttributes: {
      "deployment.environment": import.meta.env.MODE || "development",
    },
  };

  // Only add apiKey if explicitly set (omit for self-hosted ClickStack)
  const apiKey = import.meta.env.VITE_HYPERDX_API_KEY;
  if (apiKey) {
    initConfig.apiKey = apiKey;
  }

  import("@hyperdx/browser")
    .then(({ default: HyperDX }) => HyperDX.init(initConfig))
    .catch((err) => console.error("HyperDX failed to load", err));
}

// Import GSAP
import { gsap } from "gsap";

// Import Stimulus
import { Application } from "@hotwired/stimulus";

// Start Stimulus application
const app = Application.start();

// Auto-register Stimulus controllers
const modules = import.meta.glob("./controllers/**/*.js", { eager: true });

Object.entries(modules).forEach(([filename, module]) => {
  // Convert the filename to a controller name
  const controllerName = filename
    // Remove the leading "./" and "controllers/"
    .replace(/^\.\//, "")
    .replace(/^controllers\//, "")
    // Remove the ".js" extension
    .replace(/\.js$/, "")
    // Replace underscores with dashes
    .replace(/_/g, "-")
    // Replace slashes with double dashes
    .replace(/\//g, "--");

  // Register the controller with the Stimulus application
  app.register(controllerName, module.default);
});

// Expose Stimulus application globally
window.Stimulus = app;
