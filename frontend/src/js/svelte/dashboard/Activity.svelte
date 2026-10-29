<script>
  import ActivityFeed from "./ActivityFeed.svelte";

  // Root of the activity page (templates/dashboard/activity.html). Owns the
  // refresh state; ActivityFeed only renders it and asks for a refresh.
  let { activity, urls } = $props();

  // Server-rendered entries are shown until a refresh replaces them.
  let refreshed = $state(null);
  let refreshing = $state(false);
  let error = $state("");

  const entries = $derived(refreshed ?? activity.entries);

  async function refreshActivity() {
    refreshing = true;
    error = "";
    try {
      // GET only, so no CSRF token is needed. A panel that POSTs would have to
      // solve CSRF exposure first — nothing provides it to JS yet.
      const res = await fetch(urls.activity, { credentials: "same-origin" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      refreshed = await res.json();
    } catch (err) {
      error = "Could not refresh activity. Please try again.";
      console.error("activity: refresh failed", err);
    } finally {
      refreshing = false;
    }
  }
</script>

<ActivityFeed {entries} {refreshing} {error} onrefresh={refreshActivity} />
