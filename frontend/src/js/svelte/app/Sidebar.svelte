<script>
  // App shell navigation.
  //
  // Mounted into the `.sidebar` element in base_app.html, which is marked
  // hx-preserve — so this component is created ONCE and survives every boosted
  // htmx navigation. It therefore cannot rely on server-rendered active state:
  // it derives the active item from location.pathname and refreshes on
  // `htmx:after:history:push`. Layout/visibility stay with Basecoat CSS + the sidebar
  // Stimulus controller; this component only renders <nav> contents.
  let { groups, name = "App" } = $props();

  // Matches the form id in base_app.html, which holds the CSRF token.
  const LOGOUT_FORM_ID = "sidebar-logout";

  let path = $state(window.location.pathname);

  $effect(() => {
    const sync = () => {
      path = window.location.pathname;
    };
    // history:push covers boosted visits; popstate covers back/forward.
    document.addEventListener("htmx:after:history:push", sync);
    window.addEventListener("popstate", sync);
    return () => {
      document.removeEventListener("htmx:after:history:push", sync);
      window.removeEventListener("popstate", sync);
    };
  });

  // Longest match wins, so /dashboard/user/profile/ does not also mark
  // /dashboard/ active.
  const activeHref = $derived(
    groups
      .flatMap((g) => g.items.map((i) => i.href))
      .filter((h) => path.startsWith(h))
      .sort((a, b) => b.length - a.length)[0] ?? null,
  );

  // Lucide icon bodies, verbatim, keyed by the names the payload sends. Kept as
  // markup (not flattened path data) so rounded corners survive. These are
  // developer-authored constants in this file — never interpolate request data.
  const icons = {
    dashboard:
      '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
    activity:
      '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/>',
    user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    users:
      '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    mail: '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    key: '<path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/>',
    smartphone: '<rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    shield:
      '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    // lucide "power": the "log-out" door read like the sidebar collapse toggle.
    logout: '<path d="M12 2v10"/><path d="M18.4 6.6a9 9 0 1 1-12.77.04"/>',
  };
</script>

<nav>
  <header>
    <span class="font-heading flex h-12 items-center px-2 text-base font-semibold tracking-tight">
      {name}
    </span>
  </header>

  <section>
    {#each groups as group (group.label)}
      <div role="group">
        <h3>{group.label}</h3>
        <ul>
          {#each group.items as item (item.href)}
            <li>
              <a
                href={item.href}
                aria-current={item.href === activeHref ? "page" : undefined}
                hx-boost={item.boost === false ? "false" : undefined}
                data-tooltip={item.label}
                data-side="right"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  aria-hidden="true">{@html icons[item.icon] ?? ""}</svg
                >
                <span>{item.label}</span>
              </a>
            </li>
          {/each}
        </ul>
      </div>
    {/each}
  </section>

  <footer>
    <ul>
      <li>
        <!-- Basecoat lays out item rows only under nav > section, not footer. -->
        <button
          type="submit"
          form={LOGOUT_FORM_ID}
          class="text-destructive hover:bg-destructive/10 hover:text-destructive active:bg-destructive/10 active:text-destructive flex w-full cursor-pointer items-center"
          data-tooltip="Log out"
          data-side="right"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true">{@html icons.logout}</svg
          >
          <span>Log out</span>
        </button>
      </li>
    </ul>
  </footer>
</nav>
