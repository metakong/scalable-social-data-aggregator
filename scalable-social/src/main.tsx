import { Devvit } from '@devvit/public-api';

/**
 * Scalable Social — Devvit Scheduler Sensor
 *
 * Runs a daily scheduled job that fetches the installed subreddit's posts
 * from the last 24 hours, applies a demand-intent regex filter, increments
 * Redis category counters, and dispatches matching posts as a batched
 * webhook payload to the intelligence backend.
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Regex intent filter — captures posts expressing latent product demand. */
const INTENT_PATTERN =
  /(somebody should make|is there an app|wish there was an app|app idea|we need a website|would pay for)/i;

/** Redis key prefix for category counters. */
const REDIS_COUNTER_PREFIX = 'demand_counter:';

/** Redis key for the ordered leaderboard. */
const REDIS_LEADERBOARD_KEY = 'demand_leaderboard';

/** The production webhook endpoint. */
const WEBHOOK_URL = 'https://webhook.legacysweatequity.com/api/webhooks/devvit';

/** 24 hours in milliseconds. */
const TWENTY_FOUR_HOURS_MS = 24 * 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

Devvit.configure({
  http: true,
  redis: true,
  redditAPI: true,
});

// ---------------------------------------------------------------------------
// Utility: classify a post title into a demand category
// ---------------------------------------------------------------------------

function classifyCategory(title: string): string {
  const lower = title.toLowerCase();
  if (lower.includes('app idea')) return 'App Ideas';
  if (lower.includes('wish there was an app')) return 'Wished-For Apps';
  if (lower.includes('somebody should make')) return 'Build Requests';
  if (lower.includes('is there an app')) return 'App Discovery';
  if (lower.includes('we need a website')) return 'Website Requests';
  if (lower.includes('would pay for')) return 'Paid Demand';
  return 'General Demand';
}

// ---------------------------------------------------------------------------
// Scheduler Job: Daily Demand Scan
// ---------------------------------------------------------------------------

Devvit.addSchedulerJob({
  name: 'daily_demand_scan',
  onRun: async (_event, context) => {
    const { reddit, redis } = context;

    console.log('[Scheduler] Starting daily demand scan…');

    // Determine the installed subreddit
    const subreddit = await reddit.getCurrentSubreddit();
    const subredditName = subreddit.name;

    console.log(`[Scheduler] Scanning r/${subredditName} for demand signals…`);

    // Fetch recent posts (new, up to 100)
    const posts = await reddit.getNewPosts({
      subredditName,
      limit: 100,
    }).all();

    // Filter to last 24 hours
    const cutoff = new Date(Date.now() - TWENTY_FOUR_HOURS_MS);
    const recentPosts = posts.filter((post) => {
      const created = new Date(post.createdAt);
      return created >= cutoff;
    });

    console.log(
      `[Scheduler] Found ${recentPosts.length} posts from the last 24 hours.`
    );

    // Apply intent filter and build batch
    const matchedBatch: Array<{ title: string; body: string; subreddit: string }> = [];

    for (const post of recentPosts) {
      const title = post.title ?? '';
      const body = post.body ?? '';
      const combinedText = `${title} ${body}`;

      if (!INTENT_PATTERN.test(combinedText)) continue;

      // Classify and increment Redis counter
      const category = classifyCategory(title);
      const counterKey = `${REDIS_COUNTER_PREFIX}${category}`;
      const newCount = await redis.incrBy(counterKey, 1);

      // Update the sorted leaderboard (score = count)
      await redis.zAdd(REDIS_LEADERBOARD_KEY, {
        member: category,
        score: newCount,
      });

      matchedBatch.push({
        title,
        body,
        subreddit: subredditName,
      });
    }

    console.log(
      `[Scheduler] ${matchedBatch.length} posts matched the intent filter.`
    );

    if (matchedBatch.length === 0) {
      console.log('[Scheduler] No demand signals found. Skipping webhook.');
      return;
    }

    // Dispatch batched payload to the intelligence backend
    try {
      const response = await fetch(WEBHOOK_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(matchedBatch),
      });

      console.log(
        `[Scheduler] Webhook dispatched — status: ${response.status}, batch size: ${matchedBatch.length}`
      );
    } catch (error) {
      console.error('[Scheduler] Webhook delivery failed:', error);
    }
  },
});

// ---------------------------------------------------------------------------
// Trigger: Schedule the job on app install
// ---------------------------------------------------------------------------

Devvit.addTrigger({
  event: 'AppInstall',
  onEvent: async (_event, context) => {
    const { scheduler } = context;

    // Schedule the daily scan to run once every 24 hours
    await scheduler.runJob({
      name: 'daily_demand_scan',
      cron: '0 6 * * *', // 6:00 AM UTC daily
    });

    console.log('[Install] Scheduled daily_demand_scan at 6:00 AM UTC.');
  },
});

// ---------------------------------------------------------------------------
// Custom Post: Demand Dashboard (renders the React webview)
// ---------------------------------------------------------------------------

Devvit.addCustomPostType({
  name: 'Demand Dashboard',
  description: 'Top demand signals from the last 24 hours',
  render: (context) => {
    return (
      <webview
        id="demand-dashboard"
        url="client/index.html"
        width="100%"
        height="480px"
        onMessage={async (msg) => {
          // Listen for the request from index.html
          if (msg.action === 'getLeaderboard') {
            try {
              // Fetch the top 5 highest-scored categories from Redis
              const results = await context.redis.zRange(REDIS_LEADERBOARD_KEY, 0, 4, {
                by: 'score',
                reverse: true,
              });
              
              // Map Redis results into the format expected by the frontend
              const formattedEntries = results.map(r => ({
                category: r.member,
                count: r.score
              }));

              // Send the data back down to the webview
              context.ui.webView.postMessage('demand-dashboard', {
                type: 'devvit-message',
                data: {
                  action: 'leaderboardData',
                  entries: formattedEntries,
                },
              });
            } catch (error) {
              console.error('[Dashboard] Error fetching Redis leaderboard:', error);
            }
          }
        }}
      />
    );
  },
});

export default Devvit;
