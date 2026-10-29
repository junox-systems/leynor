<script>
  import Panel from "./Panel.svelte";

  // Pure props — no fetching. Everything here comes from allauth via
  // apps/dashboard/panels.py::account_payload.
  let { checks, lastLogin = null } = $props();

  const done = $derived(checks.filter((c) => c.done).length);

  const when = new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
</script>

<Panel
  title="Account & security"
  description={`${done} of ${checks.length} steps complete.`}
>
  <ul class="divide-border divide-y">
    {#each checks as check (check.label)}
      <li class="flex items-center justify-between gap-4 py-3">
        <div class="flex min-w-0 items-center gap-3">
          {#if check.done}
            <span
              class="grid size-6 shrink-0 place-items-center rounded-full bg-emerald-600/15 text-emerald-700 dark:text-emerald-400"
              aria-hidden="true"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" class="size-3.5"><path d="M20 6 9 17l-5-5" /></svg>
            </span>
          {:else}
            <span
              class="border-muted-foreground/40 grid size-6 shrink-0 place-items-center rounded-full border-2 border-dashed"
              aria-hidden="true"
            ></span>
          {/if}
          <div class="min-w-0">
            <p class="font-medium">
              {check.label}
              <span class="sr-only">
                — {check.done ? "complete" : "incomplete"}
              </span>
            </p>
            {#if check.detail}
              <p class="text-muted-foreground truncate text-xs">{check.detail}</p>
            {/if}
          </div>
        </div>
        <a
          class="btn shrink-0"
          data-variant={check.done ? "ghost" : "outline"}
          data-size="sm"
          href={check.href}
        >
          {check.action}
        </a>
      </li>
    {/each}
  </ul>

  {#if lastLogin}
    <p class="text-muted-foreground mt-4 text-xs">
      Last signed in
      <time datetime={lastLogin}>{when.format(new Date(lastLogin))}</time>
    </p>
  {/if}
</Panel>
