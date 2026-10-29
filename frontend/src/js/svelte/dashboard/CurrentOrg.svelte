<script>
  import Panel from "./Panel.svelte";

  // Pure props — from apps/dashboard/panels.py::org_payload. `org` is null
  // when the user belongs to no organization (empty state). URLs come from
  // Django; switching organizations is the app bar's job, not this panel's.
  let { org = null, urls } = $props();
</script>

{#if org}
  <Panel
    title={org.name}
    description={`${org.member_count} ${org.member_count === 1 ? "member" : "members"} · current organization`}
  >
    <p class="text-muted-foreground text-sm">
      Your roles:
      {#each org.roles as role, i (role)}
        <span class="badge" data-variant={role === "owner" ? "primary" : "secondary"}>{role}</span>{i < org.roles.length - 1 ? " " : ""}
      {/each}
    </p>
    {#snippet action()}
      <a class="btn" data-variant="outline" data-size="sm" href={urls.org}>Manage</a>
    {/snippet}
  </Panel>
{:else}
  <Panel title="Organization" description="You're not in any organization yet.">
    <a class="btn" data-variant="outline" data-size="sm" href={urls.orgs}>Create or join one</a>
  </Panel>
{/if}
