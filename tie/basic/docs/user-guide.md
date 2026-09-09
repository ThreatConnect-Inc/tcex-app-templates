# Intelligence Engine User Guide

> **Template placeholder.** This is the starter guide shipped with the TIE template.
> Replace it with the guide for your app before release — see
> [Replacing This Guide](#replacing-this-guide) at the bottom. It is served as-is by
> `GET /api/docs` and rendered on the **Documentation** page in the app UI, so whatever
> is in this file is what an operator reads.

## Table of Contents

- [Overview](#overview)
- [Dependencies](#dependencies)
- [Deployment](#deployment)
- [First-Time Setup](#first-time-setup)
- [Settings](#settings)
- [How Ingestion Works](#how-ingestion-works)
- [Screens](#screens)
- [Troubleshooting](#troubleshooting)
- [Replacing This Guide](#replacing-this-guide)

## Overview

This app is a ThreatConnect Intelligence Engine. It runs as a long-lived service inside
ThreatConnect, polls a third-party intelligence source on a schedule, converts what it
finds into ThreatConnect groups and indicators, and uploads them into a single owner.

It also serves its own management UI, where an operator can watch jobs run, queue an
ad-hoc job for a specific time range, review upload errors, and change settings without
redeploying.

> Describe what *your* app ingests here — which source, which object types, and which
> ThreatConnect objects they become.

## Dependencies

**ThreatConnect**

- A ThreatConnect server meeting the `minServerVersion` declared in `app_spec.yml`.
- An owner (Source or Organization) for the app to write into.
- An API user with write access to that owner.

**Vendor**

> List what the source side requires — an account, an API key, the entitlements or
> licensed collections the key needs, and any IP allow-listing.

## Deployment

1. Install the packaged app in **System Settings → Apps**.
2. Deploy it to an owner through the **Feed Deployer**, filling in the deploy-time
   configuration (service URL, API key, and anything else declared in `app_spec.yml`).
3. Start the service and confirm it reaches **Running**.

Deploy-time values are read from the app inputs on every boot and are never persisted by
the app. To change one — including rotating the API key — redeploy. They are shown
read-only on the **Settings** page so you can confirm what the engine is using.

## First-Time Setup

On first boot the app opens a short setup stepper. It walks the editable settings in
order, validates them, and only then lets ingestion begin: the scheduler will not queue
jobs and ad-hoc requests are rejected until setup is marked complete.

Each step can be validated before it is saved. Validation runs real checks against the
source — a connectivity test, and a check that every configured option still exists — so a
bad value is caught at setup rather than on the first job.

## Settings

Everything on the **Settings** page is stored in the app's JSON DB and survives restarts.
A change takes effect on the next cycle; no restart is needed.

| Section | What it controls |
| :--- | :--- |
| Connection | Deploy-time values, read-only. Redeploy to change them. |
| Ingestion | What the engine pulls from the source. App-specific. |
| Notifications | Which events reach the ThreatConnect notification center, and how often. |
| Advanced Settings | Poll frequency, failure threshold, and retry count. Defaults suit most deployments. |

Every save is recorded, so the settings history shows what changed, when, and from what
value.

## How Ingestion Works

Each job moves through three stages, and the **Jobs** page shows where a job is and how
long each stage took:

1. **Download** — asks the source for everything in the job's time window and writes the
   raw response to disk.
2. **Convert** — reads that raw data and applies the mappings, producing ThreatConnect
   batch format.
3. **Upload** — submits the batch to ThreatConnect and records any rejections.

The scheduler queues a new job every poll interval, covering the window since the previous
job — so a longer interval means larger, less frequent jobs rather than missed data. A job
that fails is retried up to the configured maximum before it is abandoned.

## Screens

| Screen | What it is for |
| :--- | :--- |
| Dashboard | Ingestion volume and the current health of the engine. |
| Jobs | Every job, its stage timings and counts, and ad-hoc job creation. |
| Tasks | The running pipeline tasks and their heartbeats. |
| Download | Fetch a single object from the source on demand. |
| Batch Errors | Objects ThreatConnect rejected during upload, with the reason. |
| Notifications | Every event raised, whether or not it was sent. |
| Documentation | This guide. |
| Settings | The editable configuration described above. |

## Troubleshooting

**The service will not start.** Check the app log for the preflight checks. They run
before anything else and fail loudly — an unreachable source API, missing credentials, or
an unwritable working directory are the usual causes.

**A settings change will not save.** Validation blocks a save it knows is wrong. The
message names the field and the reason; fix that value and validate again.

**Jobs are not being queued.** Confirm first-time setup is complete — the scheduler skips
every tick until it is. After that, check the poll frequency: the next job is not queued
until a full interval has passed since the last one ended.

**Jobs succeed but nothing appears in ThreatConnect.** Check the **Batch Errors** page. If
it is empty, the source returned nothing for that window, or the ingestion settings are
filtering it out.

**Healthy jobs are marked failed.** The failure threshold is too short. Keep it well above
two poll intervals.

## Replacing This Guide

- The file is `docs/user-guide.md`, and the path is fixed — `core/api/endpoint/tcvf/docs_resource.py`
  serves that one file and nothing else. Do not move or rename it.
- The page takes its title from this document's first `# ` heading, so keep exactly one and
  make it your app's name.
- Table of Contents links are plain markdown anchors. Slugs are lowercased, punctuation is
  dropped, and spaces become hyphens — so `## Batch Errors` is `#batch-errors`.
- Replace every `>` callout above with the specifics for your app, and add a **Data
  Mappings** section describing what each source object becomes in ThreatConnect. That is
  the section operators reach for most and the one no template can write for you.
