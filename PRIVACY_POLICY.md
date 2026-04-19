# Privacy Policy

**Effective Date:** April 19, 2026
**Last Updated:** April 19, 2026

## Overview

Scalable Social Data Aggregator ("the Application") is an open-source tool that analyzes publicly available Reddit post text to identify trending product demand signals. This Privacy Policy explains how data is collected, processed, and stored.

## Data We Process

The Application processes **publicly available Reddit post content** (post titles and body text) from subreddits where the Devvit sensor app is installed by a subreddit moderator.

### What We Do NOT Collect

- **No personal user data is stored.** We do not collect, store, or process Reddit usernames, user IDs, email addresses, IP addresses, or any other personally identifiable information (PII).
- **No raw post text is stored.** The original Reddit post content is processed transiently by the intelligence engine and is never persisted to any database.
- **No authentication tokens or credentials** from end users are collected.

### What We Do Store

- **AI-generated summaries** derived from aggregated post analysis (titles, SWOT analyses, opportunity ratings).
- **Aggregated category counters** representing trending demand topics — these contain no individually attributable data.
- **Subreddit names** as the source label for aggregated intelligence.

## Data Processing

Post text is sent to Google's Gemini API for natural language analysis. This processing is governed by [Google's AI Terms of Service](https://ai.google.dev/terms). No Reddit user data is included in API requests — only the post text content.

## Data Retention

- Aggregated intelligence data is retained indefinitely unless manually deleted by the system operator.
- Raw post text is processed in-memory only and is never written to persistent storage.

## Third-Party Services

| Service | Purpose | Privacy Policy |
|---------|---------|---------------|
| Google Gemini API | Text analysis and SWOT generation | [Google AI Privacy](https://ai.google.dev/terms) |
| Reddit (via Devvit) | Source of public post data | [Reddit Privacy Policy](https://www.reddit.com/policies/privacy-policy) |

## Open Source Transparency

This Application is fully open source. You may audit the complete source code to verify these privacy claims at any time by reviewing this repository.

## Operator Responsibility

If you self-host this Application, **you are the data controller** for any data processed by your instance. You are responsible for compliance with applicable data protection laws in your jurisdiction (e.g., GDPR, CCPA).

## Changes to This Policy

We may update this Privacy Policy from time to time. Changes will be committed to this repository with a clear changelog in the git history.

## Contact

For privacy-related inquiries, please open an issue in this repository.
