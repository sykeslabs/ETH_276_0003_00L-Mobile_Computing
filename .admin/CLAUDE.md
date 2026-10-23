# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the course material,
notebooks, and lecture assets in this repository.

## What this repository is

This repo holds the teaching material for **both of Dr. Stefan Mangold's modules** in the
[CAS ETH in Cloud and Mobile Computing](https://inf.ethz.ch/continuing-education/cas-cloudandmobilecomputing.html):
the **Mobile Computing** module and the **Wireless Data Communication** module. They share
foundational wireless material (radio physics, Wi-Fi, Bluetooth, cellular, satellite), which is why
one repo backs both; the hands-on simulators, devices, and mobile-AI labs belong primarily to the
Mobile Computing module.

The primary user of this file is the **professor developing the course**. Claude's job here is to act
as an informed collaborator who already understands the program — what it covers, who it is for, and
the direction it is heading — before editing any lecture or notebook. This is course material, not a
software product: there is no build/lint/test pipeline to optimize for.

This material is copyrighted (© Stefan Mangold, ETH Zurich) and open to invited contributors only.

## Who the learners are (read this before editing content)

The audience is **business managers**, not CS students. A prior technical degree is **not**
required — many learners come from business, economics, law, or social-science backgrounds; others
are technical managers refreshing fundamentals. Admission requires an ETH-recognized Master's-level
degree or equivalent (a Bachelor's may be considered exceptionally) and at least 5 years of
professional experience, including some experience allocating corporate resources (line/project
management).

The goal of the program is to **improve technology decision-making** and help managers communicate
with technical teams — **not** to produce engineers.

This is the most important constraint when editing content. The instinct to add dense math, jargon,
or code complexity (normally "good" in a code repo) is usually wrong here. **Reduce the prerequisite
load while preserving decision relevance** — explain the "so what," not the derivation. When in
doubt, favor intuition and managerial consequence over engineering depth.

The CAS is part-time: Friday full day + Saturday half day, every other week, ~300 hours total, 100%
English. The Mobile Computing module is delivered in a Saturday block format (lecture time followed
by hands-on group work).

## Repository structure (branch-dependent — see below)

The layout differs between branches. **`dev2026` is canonical**; describe and edit using its layout:

- `01_Lectures/` — 16 lecture decks (PDF) numbered `01`–`16` plus an appendix and a README. The
  sequence runs: foundations (intro, handling data, networking/wireless foundations) → a survey of
  wireless technologies (Wi-Fi PHY & MAC, Bluetooth/Zigbee, LiFi/VLC, audio, cellular, satellite) →
  applications (consumer/medical devices, algorithmic decision-making, spectrum etiquette, local
  LLMs, socio-economic/humanitarian) → a tournament-style finale. Lecture titles here are the
  ground truth for the topics covered.
- `02_Notebooks/` — Jupyter notebooks (46 on `dev2026`) organized into themes:
  `00_Intro`, `01_Data_and_Signals`, `02_Data_Communication`, `03_Mobile_Systems`,
  `04_Mobile_Algorithms`, `05_Mobile_AI`, `06_Cloud_Computing`.
- `03_Assignments/` — graded assignments (`Assignment-01` data handling, `Assignment-02` network
  self-management, `Assignment-03` mobile algorithms), plus `Submission-Guidelines.md` and
  `VlcSerial.md` (VLC serial-communication setup).
- `.admin/` — shared tooling: `.admin/notebooks/requirements.txt`, `.admin/notebooks/utils.ipynb`,
  README header/footer fragments, and `update_footers.py`.

On the frozen `main` branch the same content lives under older names (`Course Material/`,
`Hands-On Notebooks/Notebooks/` with spaced theme names, `Hands-On Notebooks/Admin/`) and has 39
notebooks. Do not use those paths for new work.

## Repository state and branching

- `main` — the **frozen 2025 reference** material. Treat it as read-only history.
- `dev2026` — the **canonical active branch** where all new course development happens. New work
  follows its `NN_` underscore naming and the layout above.

**Always check the current branch before editing.** If the checkout is on `main`, do not edit
content there — switch to (or create a local) `dev2026` first, or warn the professor.

## Course direction

AI now produces explanations and summaries for free. The course leans into what AI cannot do *for*
the learner: observing real behavior, changing something, measuring the effect, and **justifying a
decision from the evidence they produced and interpreted**. Framed for this audience, that means
decision-making backed by evidence — not engineering rigor for its own sake.

Guidelines for evolving the material:

- **Evidence-backed over purely descriptive.** Prefer notebook questions that ask learners to
  measure, compare, and explain a gap over "explain this concept" questions (which an AI can answer
  without understanding). Qualitative managerial reasoning — risk, cost, stakeholder and operational
  tradeoffs — still matters; the point is that conclusions should be anchored to evidence.
- **The lab heuristic.** Every lab should answer four questions: *What are we observing? What are we
  changing? What are we measuring? Why did the result happen?*
- **Ownership.** Put learners in situations where they own a result and defend it (e.g., short group
  presentations), so understanding can't be outsourced to AI.
- **Decision-making as the target skill.** The aim is managerial reasoning — e.g., choosing a
  wireless technology (Wi-Fi / BLE / cellular / satellite) for a business scenario and defending the
  tradeoff — with measurement serving as the evidence behind the decision, not an end in itself.
