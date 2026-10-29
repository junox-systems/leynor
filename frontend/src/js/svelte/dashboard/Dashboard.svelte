<script>
  import AccountStatus from "./AccountStatus.svelte";
  import CurrentOrg from "./CurrentOrg.svelte";

  // The one Svelte root on the dashboard. Django mounts this via svelte-bridge
  // with the whole payload as props (see templates/dashboard/index.html).
  // It owns the layout grid and any state shared across panels; children get
  // props and callbacks, never their own stores or context.
  let { account, org } = $props();
</script>

<div class="grid gap-6 lg:grid-cols-2">
  <CurrentOrg org={org.org} urls={org.urls} />
  <AccountStatus checks={account.checks} lastLogin={account.last_login} />
</div>
