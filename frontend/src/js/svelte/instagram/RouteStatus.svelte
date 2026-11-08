<script>
  // Live line for a pitch or a reel route (templates/instagram/pitch.html,
  // detail.html). Polls the DMR status endpoint while work runs; when the
  // server's version moves past the one this page was rendered from, it says
  // so and links to the page. It never navigates on its own: the person may
  // be reading.
  import { untrack } from "svelte";

  let props = $props();
  const { kind, urls } = untrack(() => props);

  const POLL_MS = 3000;
  // Props are read once at mount; the server's later state arrives by fetch.
  const initial = untrack(() => ({
    status: props.status,
    step: props.step,
    started: props.started,
    error: props.error,
    version: props.version,
  }));
  const rendered = initial.version;

  let live = $state(initial);
  let now = $state(Date.now());

  const working = $derived(live.status === "running" || live.status === "queued");
  const stale = $derived(live.version !== rendered && !working);

  const elapsed = $derived.by(() => {
    if (!working || !live.started) return "";
    const seconds = Math.max(0, Math.round((now - Date.parse(live.started)) / 1000));
    const m = Math.floor(seconds / 60);
    const s = String(seconds % 60).padStart(2, "0");
    return `${m}:${s}`;
  });

  const label = $derived.by(() => {
    if (kind === "pitch") {
      if (working) return "Writing three takes";
      if (live.status === "failed") return "The takes could not be written";
      return "Your three takes are ready";
    }
    if (live.status === "running") return `Running ${live.step}`;
    if (live.status === "queued") return `${live.step} is next in the queue`;
    if (live.status === "failed") return `${live.step} stopped`;
    if (live.status === "waiting") return `${live.step} is ready for you`;
    return "The reel is finished";
  });

  async function refresh() {
    if (document.hidden) return;
    try {
      // GET only: islands hold no CSRF token.
      const res = await fetch(urls.status, { credentials: "same-origin" });
      if (!res.ok) return;
      const data = await res.json();
      live = {
        status: data.status,
        step: data.step,
        started: data.started,
        error: data.error,
        version: data.version,
      };
    } catch (err) {
      console.error("route-status: refresh failed", err);
    }
  }

  $effect(() => {
    if (!working) return;
    const poll = setInterval(refresh, POLL_MS);
    const tick = setInterval(() => (now = Date.now()), 1000);
    return () => {
      clearInterval(poll);
      clearInterval(tick);
    };
  });
</script>

<div role="status" aria-live="polite">
  {#if working}
    <p class="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
      <span class="relative flex size-2" aria-hidden="true">
        <span
          class="bg-primary/60 absolute inline-flex size-full animate-ping rounded-full motion-reduce:hidden"
        ></span>
        <span class="bg-primary relative inline-flex size-2 rounded-full"></span>
      </span>
      <span class="font-medium">{label}</span>
      {#if elapsed}
        <span class="text-muted-foreground tabular-nums">{elapsed}</span>
      {/if}
      <span class="text-muted-foreground basis-full ps-4 sm:basis-auto sm:ps-0">You can leave this page; it keeps going.</span>
    </p>
  {:else if stale}
    <div class="alert" data-variant={live.status === "failed" ? "destructive" : undefined}>
      <h3>{label}</h3>
      <section class="flex flex-wrap items-center justify-between gap-3">
        <span>{live.status === "failed" && live.error ? live.error : "This page shows an earlier state."}</span>
        <a class="btn" data-size="sm" href={urls.page}>Show it</a>
      </section>
    </div>
  {/if}
</div>
