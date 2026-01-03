<script lang="ts">
	import '../app.css';

	let { children } = $props();
</script>

<svelte:head>
	<title>Sermon Finder - Find Peace in God's Word</title>
</svelte:head>

{@render children()}
