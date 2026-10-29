<script>
  // Shared card shell for dashboard panels. Markup follows Basecoat's `.card`
  // contract (> header with h2/p, > section for body) — add no CSS here.
  let { title, description = "", action, children } = $props();

  const headingId = $props.id();
</script>

<section class="card" aria-labelledby={headingId}>
  <header>
    <h2 id={headingId}>{title}</h2>
    {#if description}
      <p>{description}</p>
    {/if}
    {#if action}
      <div data-slot="card-action">{@render action()}</div>
    {/if}
  </header>
  <section>
    {@render children()}
  </section>
</section>
