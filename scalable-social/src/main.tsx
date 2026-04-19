import { Devvit } from '@devvit/public-api';

/**
 * Scalable Social — Devvit Sensor App
 *
 * Listens for new posts in the installed subreddit via the onPostSubmit
 * trigger.  When a post matches the demand-intent regex, the sensor fires
 * an HTTP POST webhook to the intelligence backend for async SWOT analysis.
 */

// The regex intent filter — captures posts expressing latent product demand
const INTENT_PATTERN =
  /(somebody should make|is there an app|wish there was an app|app idea|we need a website|would pay for)/i;

// Configure the Devvit app capabilities
Devvit.configure({
  http: true, // required for outbound fetch()
});

// ---------------------------------------------------------------------------
// onPostSubmit Trigger
// ---------------------------------------------------------------------------
Devvit.addTrigger({
  event: 'PostSubmit',
  onEvent: async (event, context) => {
    const post = event.post;
    if (!post) return;

    const title = post.title ?? '';
    const body = post.body ?? '';
    const subreddit = post.subreddit?.name ?? 'unknown';

    // Run the intent filter against title + body
    const combinedText = `${title} ${body}`;
    if (!INTENT_PATTERN.test(combinedText)) {
      console.log(
        `[Sensor] Post in r/${subreddit} did not match intent filter. Skipping.`
      );
      return;
    }

    console.log(
      `[Sensor] Demand signal detected in r/${subreddit}: "${title.slice(0, 80)}"`
    );

    // Build the webhook payload
    const payload = {
      title,
      body,
      subreddit,
    };

    // POST to the intelligence backend webhook
    // The WEBHOOK_URL should be set via `devvit settings` or as an install setting.
    // Default to localhost for local development with ngrok.
    const webhookUrl =
      (await context.settings.get<string>('webhook_url')) ??
      'http://localhost:8000/api/v1/webhooks/devvit';

    try {
      const response = await fetch(webhookUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      console.log(
        `[Sensor] Webhook dispatched to ${webhookUrl} — status: ${response.status}`
      );
    } catch (error) {
      console.error(`[Sensor] Webhook delivery failed:`, error);
    }
  },
});

// ---------------------------------------------------------------------------
// Install Settings — allow the user to configure the webhook URL
// ---------------------------------------------------------------------------
Devvit.addSettings([
  {
    type: 'string',
    name: 'webhook_url',
    label: 'Intelligence Backend Webhook URL',
    helpText:
      'The full URL of the Flask webhook endpoint (e.g. https://<ngrok-id>.ngrok.io/api/v1/webhooks/devvit)',
    defaultValue: 'http://localhost:8000/api/v1/webhooks/devvit',
  },
]);

export default Devvit;
