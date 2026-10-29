<script>
  import Panel from "./Panel.svelte";

  // Data and refresh state are owned by the Activity root — this child just
  // renders them and asks for a refresh.
  let { entries, refreshing = false, error = "", onrefresh } = $props();

  const when = new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
</script>

<Panel title="Recent activity" description="Audited changes you have made.">
  {#snippet action()}
    <button
      type="button"
      class="btn"
      data-variant="outline"
      data-size="sm"
      onclick={onrefresh}
      disabled={refreshing}
    >
      {refreshing ? "Refreshing…" : "Refresh"}
    </button>
  {/snippet}

  {#if error}
    <div class="alert" data-variant="destructive" role="alert">{error}</div>
  {:else if entries.length === 0}
    <!-- `.empty` sets border-dashed but not a width — `border` supplies it. -->
    <div class="empty border">
      <header>
        <h3>No activity yet</h3>
        <p>
          Changes appear here once they are audited. Only models registered with
          <code class="kbd">auditlog.register()</code> are tracked — this starter kit
          registers <code class="kbd">User</code>.
        </p>
      </header>
    </div>
  {:else}
    <ul class="divide-border divide-y">
      {#each entries as entry (entry.id)}
        <li class="flex items-start justify-between gap-4 py-3">
          <div class="min-w-0">
            <p class="truncate font-medium">
              {entry.action}
              <span class="text-muted-foreground font-normal">{entry.model}</span>
              — {entry.object_repr}
            </p>
            {#if entry.fields.length}
              <p class="text-muted-foreground mt-0.5 truncate text-xs">
                Fields: {entry.fields.join(", ")}
              </p>
            {/if}
          </div>
          <time
            class="text-muted-foreground shrink-0 text-xs"
            datetime={entry.timestamp}
          >
            {when.format(new Date(entry.timestamp))}
          </time>
        </li>
      {/each}
    </ul>
  {/if}
</Panel>
