<script lang="ts">
	import type { Mood } from '$lib/types/sermon';
	import SermonCard from '$lib/components/SermonCard.svelte';
	import {
		results,
		loading,
		error,
		selectedMood,
		search,
		searchMood,
		hasResults
	} from '$lib/stores/search';

	let inputValue = $state('');

	const moods: { id: Mood; label: string }[] = [
		{ id: 'anxious', label: 'Anxious' },
		{ id: 'sad', label: 'Sad' },
		{ id: 'grieving', label: 'Grieving' },
		{ id: 'lost', label: 'Lost' },
		{ id: 'angry', label: 'Angry' },
		{ id: 'grateful', label: 'Grateful' },
		{ id: 'hopeless', label: 'Hopeless' },
		{ id: 'fearful', label: 'Fearful' },
		{ id: 'lonely', label: 'Lonely' },
		{ id: 'overwhelmed', label: 'Overwhelmed' }
	];

	function handleMoodClick(mood: Mood) {
		searchMood(mood);
	}

	function handleSubmit(e: Event) {
		e.preventDefault();
		if (inputValue.trim().length >= 3) {
			search(inputValue.trim());
		}
	}
</script>

<main class="min-h-screen bg-gradient-to-b from-amber-50/50 to-orange-50/30">
	<!-- Main content area - centered vertically when no results -->
	<div class="flex flex-col {$hasResults ? '' : 'min-h-screen justify-center'} px-4 py-12">

		<!-- Search Section -->
		<div class="w-full max-w-xl mx-auto text-center">

			<!-- Headline -->
			<h1 class="text-3xl font-bold text-gray-800 mb-2">
				How are you feeling?
			</h1>
			<p class="text-gray-500 mb-8">
				Select a mood or describe what's on your heart
			</p>

			<!-- Mood Pills -->
			<div class="flex flex-wrap justify-center gap-2 mb-8">
				{#each moods as mood}
					<button
						onclick={() => handleMoodClick(mood.id)}
						class="px-4 py-2 rounded-full text-sm font-medium transition-all duration-200
							{$selectedMood === mood.id
							? 'bg-amber-500 text-white shadow-lg shadow-amber-500/30 scale-105'
							: 'bg-white text-gray-600 shadow-sm hover:shadow-md hover:bg-amber-50 hover:text-amber-700 border border-gray-100'}"
					>
						{mood.label}
					</button>
				{/each}
			</div>

			<!-- Search Input -->
			<form onsubmit={handleSubmit} class="relative max-w-md mx-auto">
				<input
					type="text"
					bind:value={inputValue}
					placeholder="Or type how you're feeling..."
					disabled={$loading}
					class="w-full px-5 py-4 pr-28 rounded-2xl text-base
						bg-white border-2 border-gray-100 shadow-sm
						placeholder-gray-400 text-gray-800
						focus:outline-none focus:border-amber-400 focus:shadow-lg
						disabled:opacity-60 transition-all duration-200"
				/>
				<button
					type="submit"
					disabled={$loading || inputValue.trim().length < 3}
					class="absolute right-2 top-1/2 -translate-y-1/2
						px-5 py-2.5 rounded-xl text-sm font-semibold
						bg-amber-500 text-white
						hover:bg-amber-600 active:bg-amber-700
						disabled:bg-gray-200 disabled:text-gray-400
						transition-all duration-200"
				>
					{$loading ? 'Searching...' : 'Search'}
				</button>
			</form>

			<!-- Error State -->
			{#if $error}
				<p class="mt-4 text-sm text-red-500">{$error}</p>
			{/if}
		</div>

		<!-- Results Section -->
		{#if $loading}
			<div class="mt-12 text-center">
				<div class="inline-flex items-center gap-3 text-gray-500">
					<div class="w-5 h-5 rounded-full border-2 border-amber-200 border-t-amber-500 animate-spin"></div>
					<span>Finding sermons for you...</span>
				</div>
			</div>
		{:else if $hasResults}
			<div class="mt-12 w-full px-4">
				<p class="text-center text-sm text-gray-500 mb-6">
					Found {$results.length} sermon{$results.length !== 1 ? 's' : ''} for you
				</p>
				<div class="flex flex-wrap gap-4 justify-center">
					{#each $results as sermon (sermon.video_id)}
						<div class="w-72">
							<SermonCard {sermon} />
						</div>
					{/each}
				</div>
			</div>
		{/if}
	</div>
</main>
