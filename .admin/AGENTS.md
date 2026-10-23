# Mobile Computing Course Repository — Handoff Notes

This file records the current editorial direction and the changes made during the August 19-26, 2026 working sessions. Preserve existing uncommitted work and inspect `git status` before making further changes.

## October 14, 2026: 16-level repeated game and bargaining domain

- The simulator implementation now lives in `.admin/notebooks/tit_for_tat.py`. Notebook 04.4 contains a six-line launcher that locates the helper through its parent directories and runs it with IPython, matching notebook 04.3. The simulator function was moved unchanged; importing the helper does not display the UI. Tested the actual launcher and widget callbacks from both the course repository root and the notebook directory. Keep the helper with the notebook when committing. The exercises are simplified; only the first two are required and all others are optional.
- Generalized notebook `04.4_Tit-for-Tat_Spectrum_Management.ipynb` Section 4.2 to a prisoner game with 16 informing levels per player (0 = silence, 15 = full informing). For a=i/15 and b=j/15, prison costs are cA=1-a+4b and cB=1+4a-b. Mutual silence now gives (1,1), with other endpoints (5,0), (0,5), and (4,4) preserved. The current one-year illustration variants are PrisonnersDilemmaOneYear.png and PrisonnersDilemmaMultiStageOneYear.png; built-in image edit prompts are saved in PrisonnersDilemmaOneYear.prompts.md. Smaller costs are better. The original binary illustrations now explicitly show endpoint cases; preserve their transparent cropped PNGs, grayscale HTML styling, 90% centered bordered containers, and current padding.
- There is one repeated-game simulator before Section 4.3; the earlier redundant code cell and manual button game were removed. Strategies for both players are Always cooperate, Always defect, Fixed level (0-15 slider), Random (uniform over all 16 levels), and modified Tit-for-Tat (round 1 preset to level 15, then match higher informing immediately; at an equal or lower observed level, reduce own informing by one step, stopping at 0). It runs 100 rounds.
- Sections 4.2.4-4.2.6 introduce the discrete bargaining domain, Pareto efficiency, one-round Nash equilibrium, and trajectory controls. All 256 distinct outcomes are plotted with blue curved arrows between successive outcomes (100 available rounds, 99 transitions). A separate seeded drawing RNG slightly varies each arc bend; reverse jumps bend on opposite sides, slider changes preserve existing arcs, and outcome coordinates/game randomness are unchanged. The bottom text summary was removed. Also shown are 31 Pareto-efficient points in green, and the unique one-round Nash outcome (4,4), from action levels (15,15), as a red diamond. No graph title or round colorbar. An open blue circle marks the first outcome and a blue X the last displayed outcome. The default is Random against Random, showing 10 rounds. Every strategy pairing is initialized at levels (15,15) in round 1; selected strategies apply from round 2. The Nash legend reads 1-round NE. The modified Tit-for-Tat rule includes cooperative initiative when levels are equal. Two such players descend together from levels (15,15) in round 1 to (0,0) in round 16, with costs (2.2,2.2) at round 10 and (1,1) from round 16 onward. Against Always defect, the rule alternates its own level between 14 and 15 after the initial round. The (1,1) label has a guide line anchored at the emphasized exact coordinate. The graph uses 14pt axis labels, 12pt tick numbers and coordinate annotations, an 11pt two-column legend inside the northeast corner, with both axis limits extended to 5.75 to keep it clear of all feasible outcomes. The figure is 8-by-8 inches with equal axis scales and a square plotting area; legend labels include Pareto Frontier, Round 1, and Last Round. A round slider reveals the existing path without resampling; independent seeded random streams support reproducible comparisons. Explain that Pareto efficiency need not imply fairness, stage equilibrium differs from repeated-game equilibrium, and Nash bargaining solution is a separate concept. No bargaining protocol or negotiated solution is implemented.
- Reviewed all notebook prose and exercises for the generalized simulator. Added Stanford game-theory notes as reference 11 and an MIT Nash-equilibrium link; corrected malformed replacement characters in existing reading entries. Section 4.3 is now prose only, explaining how the multistage game maps to mobile devices, transmission choices, measured delay/throughput, Pareto efficiency, equality, Nash equilibrium, repeated adaptation, and imperfect observations. Its wireless simulator was removed. Section 4.3.1 distinguishes regulator, device and network-operator objectives; defines useful payload spectral efficiency and data throughput; discusses QoS and protocol overhead; and connects the tradeoffs to constraints, utilities and feasible outcomes. It uses Mangold/Berlemann/Nandagopalan (2006), Sections 5.1, 6.1 and 7.4, and Jemula802 as application context. Use the term data throughput rather than goodput in notebook prose. Retransmitted payload counts once upon successful delivery. The final mobile-computing exercise also asks about these goals and overhead. Section 4.3.2 explains licensed and licence-exempt spectrum, open access, shared licensing and authorised opportunistic reuse with incumbent protection. It distinguishes access rights from QoS guarantees and unlicensed access from unregulated or open Wi-Fi access, using paper 6 as application context. References in Section 4.3 should use our Jemula802 simulator/course Notebook 03.7 or the user's papers; the ns-3 reference was removed. The introduction, conclusion, and final application exercise were updated; the existing repeated-game simulator was preserved exactly.
- Verification: notebook schema, retained game code compilation, independent enumeration of every cost/Pareto/Nash condition, all 25 strategy pairings, all fixed levels, simultaneous copying, random reproducibility, round-slider preservation, seed-button reruns, and one-PNG rendering with no open figures passed. Reviewed PNG previews for random, stationary, and intermediate-level paths. Cleared stale saved output from the changed simulator cell. Work remains uncommitted; reload notebook editors before rerunning.

## October 13, 2026: Tit-for-Tat notebook and rocket gain sliders

- Revised `02_Notebooks/04_Mobile_Algorithms/04.4_Tit-for-Tat_Spectrum_Management.ipynb`. Section 4.2 now motivates strategic interaction without repeating the example in 4.2.1. The example uses police questioning two prisoners separately, rather than a banker and coins. Cooperate means stay silent and cooperate with the other prisoner; defect means inform on the other prisoner.
- Sentence table (A, B): `(C, C) = (2, 2)` years, `(C, D) = (5, 0)`, `(D, C) = (0, 5)`, `(D, D) = (4, 4)`. Interactive games retain the equivalent point payoffs `(3, 3)`, `(0, 5)`, `(5, 0)`, `(1, 1)`, with the explicit conversion `points = 5 - years in prison`. Higher points mean less prison time. Repeated questioning is identified as an abstract repeated-game model. The final-round example gives 32/27 points, equivalent to 18/23 total years, versus 30/30 points and 20/20 years for mutual cooperation throughout.
- Linked the course BackgroundReading repository's `Algorithms and Game Theory` guide and relevant saved readings, with inline references and reading guidance. Clarified Axelrod's 1980 tournament report, 1981 paper with Hamilton, and 1984 book. Verified that the linked collection files exist locally.
- Replaced `.admin/notebooks/picture/PrisonnersDilemma.png` and added `PrisonnersDilemmaMultiStage.png` in the same folder. Both are Hergé-inspired illustrations of separate police questioning, with prison-sentence labels, genuinely transparent PNG backgrounds, no coins, no title banners, and no bottom explanatory banner. The second illustrates `(C, C)`, `(C, D)`, then `(D, D)` as A follows Tit-for-Tat. Built-in image generation prompts and edit history are saved in `PrisonnersDilemma.prompts.md`; the final prison-sentence prompts supersede the earlier coin illustrations.
- Preserve the requested HTML presentation: first image width `60%`, second `80%`; both use `filter: grayscale(70%)`. Grayscale is applied only in HTML, not baked into the PNGs. Each image and its caption share a rounded border with padding.
- All three interactive code cells explicitly render their Matplotlib figure to PNG, close the figure, and replace the Output widget's contents. Do not restore `plt.show()` or automatic figure display in these callbacks: it caused duplicate graphs. The third cell replaces its current text summary alongside the single image. Each cell imports its own rendering dependencies.
- Replaced agent terminology throughout notebook prose, exercises, and code identifiers with opponent or player. Internal repeated-game state uses `opponent_score`, `_opponent_move`, and the history key `opponent`.
- Verification: all notebook code cells compile; checked both games against the sentence-to-point conversion; exercised all four fixed-strategy combinations, Tit-for-Tat's final-round scores, Grudger's response, reset and opponent/round changes. Repeated channel simulations with 2, 4, and 10 devices retain one image and one current summary, with correct deterministic edge-case results and no open Matplotlib figures. Both PNG alpha channels and `git diff --check` passed. These were local execution checks, not a fresh browser visual test. Reload the notebook and rerun cells to discard old rendered duplicates.
- In notebook 04.3's helper `.admin/notebooks/rocket_landing/cockpit.css`, PID gain readouts now have a fixed 64px width so Kp's two-digit maximum does not shorten its track relative to Ki/Kd. Rerun the cockpit launcher to load the CSS. Existing user edits to notebooks 04.2 and 04.3 were preserved; inspect their diffs separately when committing.
- The user will commit these changes. No commit was made in this session. Include the two new picture-folder files (the multi-stage PNG and prompts) with the notebook and illustration updates.

## September 16, 2026: Shannon–Nyquist exercise slide

- Added `notebook_exercise_01_8` to live deck 03 as page 70, after the Correlation exercise and before the closing slide. It references `01.8_Shannon_Nyquist_Sampling_Theorem.ipynb`, Section 8.10, and retains the existing exercise style and Moodle submission wording. Do not duplicate it.
- Downloaded the updated `01_Lectures/03 Mobile Computing - Handling Data in Mobile Computing.pdf`: 71 pages, 720 × 450 pt. Verified all original live slides were preserved and visually reviewed the new exercise.
- Snapshots, request payload, export, previous local PDF, preview, and validation are in `/Volumes/Lab Data/WirelessNotebooks/.codex-artifacts/nyquist-exercise-20260916/`. Notebook edits already present in the working tree were preserved.

## September 14, 2026: Marconi illustration and wireless-introduction PDF

- Generated `.admin/img/marconi_early_experiments.png` in the Titanic illustration's 3D style; its prompt and historical sources are in the adjacent `.prompt.md` file. The image was inserted after page 21 in deck 02.
- The user subsequently replaced the inserted slide with a standard-layout version. Current slide 22 ID: `g3f8d6ce2e00_2_4`; the old `marconi_1895_3d_experiments` slide no longer exists. Current slide inherits its background/footer and has a single page-number placeholder. Preserve the user's replacement; do not rerun old insertion/reset scripts.
- Downloaded the latest `01_Lectures/02 Mobile Computing - Introduction, Wireless Standards.pdf`: 35 pages, 720 × 450 pt, one slide per page. Verified Marconi on page 22, its image, and a single page indicator. Snapshot, previous PDF, preview, and validation: `.admin/presentation-workspace/output/wireless-introduction-refresh-20260914-173421/`.

## September 14, 2026: Introduction PDF refreshed after manual edits

- Downloaded the current live Introduction deck to `01_Lectures/01 Mobile Computing - Introduction.pdf`: 27 pages, 720 × 450 pt, one slide per page. Verified the text on changed slides 3, 4, 8, 10, and 11. No Google Slides edits were made.
- Local validation is in `.admin/presentation-workspace/output/introduction-refresh-20260914-171513/validation.json`. A local disk-space error required storing the export, backup, and previews on `/Volumes/Lab Data/WirelessNotebooks/.codex-artifacts/introduction-refresh-20260914-171513/`; the final lecture PDF was installed successfully in the normal local folder.

## September 14, 2026: existing exercise notebook references audited

- Read all 18 live course decks and checked 51 existing exercise slides against the current notebook filenames, folders, topics, and explicit section references. Excluded the six newly generated exercise slides in deck 03. All exercise references were correct; no exercise slides were changed. User also confirmed the suspected exercise mismatch was a mistake.
- Found one obsolete adjacent source label on Foundations slide 76: `CSMA Performance (Source: AccessProtocols.pynb)`. Updated it to `CSMA Performance (Notebook 03.5, §5.2.6)`, matching the access-protocol throughput graph in `03.5_Wi-Fi_Contention_Protocol.ipynb`. The following exercise already gave the correct full filename.
- Refreshed `01_Lectures/04 Mobile Computing - Foundations of Wireless Communications.pdf`: 83 pages, one slide per page, 720 × 450 pt. Confirmed all other live slides were unchanged and visually checked page 76. Deck 03 was not changed during this audit.
- Fresh snapshots, complete audit table, validation, and the previous Foundations PDF are in `.admin/presentation-workspace/output/exercise-reference-audit-20260914/`. `report.md` and `reference-validation.json` record the 51 checks. Do not rerun the one-time source-label correction script.

## September 14, 2026: deck 03 rebuilt, formatting approved, PDF downloaded

- User authorized a substantive rebuild from slide 15 onward, covering notebooks 01.2–01.7, with an exercise slide ending each notebook block.
- The live deck now has 70 slides: 54 new slides covering notebooks 01.2–01.7, original slides 1–14, and the previous source-coding exercise/closing slide. Exercise endings are pages 22, 31, 40, 49, 57, and 68. Content and coverage are in `.admin/presentation-workspace/output/deck03-rebuild/slides.json` and `coverage.md`; figures and math were generated from course equations and synthetic data. Speaker notes contain notebook/section references and equations.
- User explicitly approved the private temporary Slides asset file after the previous automatic-review rejection. Publication succeeded; the earlier permission block is resolved. No sharing permissions were changed. `asset-cleanup.json` records removal of the temporary file after its images were copied into the live deck.
- User then deferred PDF export and requested that new slides match slides 1–14 more closely. The 54 new slides now use Roboto Slab, the shallow title band, larger 26-point lead text, simple footers, and the split red Exercise header. Extra chapter labels and gold sidebars were removed. Native text subscripts were corrected. PNG previews were reviewed in `style-thumbnails/`; `style-after.json` / `after.json` capture the live formatting. First 14 slides and deck order were verified unchanged.
- User approved the formatting and requested the download. Refreshed `01_Lectures/03 Mobile Computing - Handling Data in Mobile Computing.pdf` from the live deck: 70 pages, 720 × 450 pt, one slide per page, no handouts or notes. Checked all 54 new slide titles, six exercise endings, Moodle text, and representative rendered pages. Export and validation are `approved-final.pdf`, `approved-export-snapshot.json`, and `approved-export-validation.json` in the rebuild workspace; the previous local PDF is backed up there. Older draft/export PDFs and `finalize.py` are obsolete and must not be used to replace this approved export.
- The one-time `prepare_remote.py`, `apply_to_deck.py`, and `match_original_style.py` scripts have already run; do not rerun them. `finish_style.py` makes final wrapping/proportion corrections and trashes the temporary asset deck. `format-review.json` records completion of that step. Preserve all source notebooks: no notebook content was changed during this slide task; an unrelated user edit to `02.2_Source_Coding.ipynb` is present.

## September 14, 2026: entropy, redundancy, and correlation order

- The current order is `01.5_Entropy.ipynb`, `01.6_Redundancy.ipynb`, then `01.7_Correlation.ipynb`. This supersedes the older sequence below. Notebook headings, local links, the notebook index, and Assignment 01 follow this order.
- Redundancy now starts from the entropy notebook's eight three-bit symbols, information content I(x), symbol entropy H(X), and average encoded length L. It introduces encoding overhead before conditional entropy and mutual information, without requiring prior correlation knowledge. Correlation follows as a way to detect certain relationships.
- Deck 03 and its local PDF were refreshed on September 14 after the 01.6/01.7 swap: slide 23 uses the Digital Time Series filename; slides 29-30 use Entropy, Redundancy, Correlation and current notebook references. Validated 32 native 720 x 450 pt pages and reviewed the three changed slides. Artifacts: `.admin/presentation-workspace/output/deck03-reference-refresh/20260914-164119/`.

## September 14, 2026: exercise coverage and Moodle

- Replaced Polybox upload text on 33 slides across 11 live decks, including the introduction's upload link. Submissions now use Moodle. Do not rerun older exercise-generation scripts unchanged: some still contain obsolete Polybox instructions.
- Added 11 exercise slides using the existing Exercise layouts, immediately before each closing slide: Source Coding in deck 03 (page 31); Basics of Data Communication, Channel Coding, Noise and Interference, Path Loss, and Shannon Capacity in deck 04 (pages 78–82); Multipath and OFDM in deck 05 (page 36); acoustic notebooks 02.10–02.13 in deck 09 (pages 37–40).
- All 57 current notebooks are now explicitly referenced by filename or numbered title across the 18 course decks. The intro overview references some notebooks without a separate exercise slide. Existing Mobile AI, Cloud, Jemula802, and rocket exercises were retained.
- Refreshed the 12 affected PDFs in `01_Lectures/`. Lecture PDFs now use the original slide dimensions, one slide per page, without notes space. The complete set has 655 pages. All new exercise slides were visually reviewed; PDF text, counts, and dimensions were verified.
- Snapshots, request payloads, notebook coverage, validation, a complete PDF ZIP, and backups of the previous local PDFs are under the ignored `.admin/presentation-workspace/output/remaining-exercises-2026-09-14/`. The new slide IDs begin with `notebook_exercise_02_`; do not duplicate them. No commit was made.

## September 8, 2026 handoff

These updates supersede the older inventory and placeholder notes below where they conflict. Inspect current files before choosing the next task; the earlier "Next editorial task" is historical, not an instruction to resume it automatically.

### Rocket landing notebook

- `02_Notebooks/04_Mobile_Algorithms/04.3_PID_For_Rocket_Landing.ipynb` is implemented and linked in `02_Notebooks/README.md` and Assignment 02 under Mobile Algorithms (Part II).
- The notebook has one collapsed launcher code cell. Its implementation lives in `.admin/notebooks/rocket_landing/lab.py`, `replay.html`, and `cockpit.css`. The launcher locates the helpers from either the repository root or the notebook folder. Keep these files with the course repository.
- The exercise is to find the highest Horizontal Wind with roughly four successful landings out of five attempts. Keep gains fixed during each comparison and vary seeds; the emphasis is PID intuition and experimentation, not statistical precision.
- Preserve the cockpit controls, Lovefield rocket artwork, animated Swiss wind flag, and single flight diagnostics panel. The panel heading is simply "Flight deck". The text explains how tilting thrust to counter horizontal wind reduces its upward component.
- Defaults: both PID gain triples `(0.1, 0.1, 0.1)`, Horizontal Wind `1`, seed `7`, sound on, volume `75%`. New attempts advance the seed automatically unless the fixed-seed radio option is selected. Replay repeats the same recorded attempt.
- Preserve playback speed, volume, mute state, and the existing audio context between attempts. Button wording is Play/Replay, without "with sound". Browser audio may require the initial user Play gesture.
- Crash audio is an explosion only; success uses a happy chime followed by the local recorded applause WAV. The WAV and its attribution are in `.admin/notebooks/sounds/`. Do not rename this to `audio`: the repository ignores directories with that name. Video references remain as links, with no embedded YouTube player.
- Notebook execution and browser checks previously covered controls, seed modes, reruns, persistent playback/audio settings, responsive sizing, and sound playback. Verification scripts and artifacts are under the ignored `.admin/presentation-workspace/output/rocket-landing-notebook/`; some older scripts predate helper extraction and should not be rerun blindly.

### Slides and lecture handout

- Added "Rocket Landing with PID" as slide 24, after the existing PID exercise, in **13 Mobile Computing - Decision Making**. The deck now has 47 slides. Deck ID: `1F4X2Dl8fLGEys1PjHPUZVepPWo4yI2Jz5I6H36tIskw`; slide ID: `rocket_landing_pid_exercise`.
- The new exercise uses the existing master/layout and red exercise header. The inherited footer still says "12 Mobile Computing - Decision Making", a pre-existing mismatch with the renamed filename; it was not changed during the exercise addition.
- Refreshed `01_Lectures/13 Mobile Computing - Decision Making.pdf` from the live deck: 47 A4 portrait pages, each with the slide above ruled notes. Page 24 contains the rocket exercise. Page dimensions and preserved slide text were checked, and the new page was visually reviewed.
- Source snapshots, a backup, validation, and export code are in the ignored `.admin/presentation-workspace/output/rocket-landing-exercise-slide/`. Do not rerun the one-time slide addition script or add a duplicate exercise. Download a fresh export when regenerating a changed deck; older bulk generators can reuse cached PDFs.

### MicroLLM helper cleanup

- The active combined project is `02_Notebooks/05_Mobile_AI/05.16_Build_Your_Own_Model.ipynb`. It now finds its helpers in `.admin/notebooks/microllm/` from the repository root or notebook folder.
- Moved `micro_llm_helpers.py`, `micro_llm_training_data.py`, and `minifacts_qkv_inspector.py` there without changing their Python contents. Model state paths remain relative to the kernel's working directory. The inspector is standalone and requires separately exported checkpoints.
- Removed the five superseded `HandsOn_*.ipynb` notebooks at the user's request, including their staged additions and references in both notebook READMEs. Do not restore them or recreate `05_Mobile_AI/misc/`.
- Executed all code cells of the active project in fresh kernels from both supported working directories, using three training steps in temporary verification copies. Imports, training, visualizations/widgets, inference, and model save/load passed. This was not a full 300-step training benchmark. Artifacts are in the ignored `output/microllm-helper-relocation/` workspace directory.

### Output cleanup and next-session housekeeping

- Checked all 54 non-ignored course notebooks. Removed 23 saved cell outputs from seven notebooks; nine notebooks needed some combination of output, execution count, widget state, or execution timestamp cleanup. Code, markdown, and presentation metadata were preserved.
- Keep committed notebooks free of generated outputs unless explicitly requested otherwise. Reload open notebook editors before saving, so stale outputs or source text are not restored.
- Work remains uncommitted with a mixture of staged and unstaged changes. Re-stage the final cleaned versions and intended deletions before committing; in particular, the staged rocket notebook can still contain its earlier outputs. No commit was made in this session. Preserve the existing changes to Digital Modulation, Path Loss, and Jemula802.
- `.admin/notebooks/` contains required course helpers/assets and belongs in Git. `.admin/presentation-workspace/` contains private credentials, local tools, backups, and generated verification artifacts; keep that entire workspace ignored and out of Git.

## Repository layout and documentation

The notebook wrapper directory was removed on August 25. Section directories now sit directly under `02_Notebooks/`:

```text
02_Notebooks/
├── 00_Intro/
├── 01_Data_and_Signals/
├── 02_Data_Communication/
├── 03_Mobile_Systems/
├── 04_Mobile_Algorithms/
├── 05_Mobile_AI/
└── 06_Cloud_Computing/
```

- Do not recreate `02_Notebooks/Notebooks/`. Notebook links to repository-root resources now use `../../` rather than `../../../`.
- `.admin/generate_html_slides.sh` and `.admin/generate_pdf_handouts.sh` use `02_Notebooks/` as their source directory.
- The former root course overview and `SETUP.md` were consolidated into the root `README.md`. `SETUP.md` and the temporary `GETTING_STARTED.md` no longer exist.
- The root README contains the course overview, numbered setup instructions and links to the indexes in `01_Lectures/README.md`, `02_Notebooks/README.md` and `03_Assignments/README.md`.
- `03_Assignments/README.md` was added using the shared navigation, banner, resource list and footer style.
- Repository handoff files now live at `.admin/AGENTS.md` and `.admin/CLAUDE.md`.

## 00 Intro sequence

The first five Intro notebooks are:

1. `00.1_Check_Course_Environment.ipynb`
2. `00.2_Check_Hardware_Connectivity.ipynb`
3. `00.3_Scientific_Literature_and_Research_Integrity.ipynb`
4. `00.4_Vibe_Coding_Best_Practices.ipynb`
5. `00.5_Learning_Git_Basics.ipynb`

The first two were renamed from the ambiguous Getting Started names. The root README is the installation and setup guide; `00.1` verifies the software environment and `00.2` verifies optional Raspberry Pi and Arduino connectivity. `00.5` introduces Git, anonymous cloning of the ETH GitLab repository, pull/status/add/commit concepts, safe handling of local changes and the Learn Git Branching tutorial.

All 50 current course notebooks use the same first-cell chapter treatment: a right-aligned 100 px ETH logo, a blank separator line and the centered chapter title. The blank line is required so Markdown titles following the raw HTML logo render as headings.

## Current notebook sequence

### 01 Data and Signals

The intended conceptual sequence is:

1. `01.5_Entropy.ipynb` — quantify unpredictability and theoretical information content.
2. `01.6_Correlation.ipynb` — identify relationships and predictable patterns. Correlation should be presented as one way to identify predictability, not as a detector of every kind of redundancy.
3. `01.7_Redundancy.ipynb` — explain predictable or repeated information.

Source Coding, formerly the Data Compression notebook in this section, was moved to Data Communication as `02.2_Source_Coding.ipynb`.

### 02 Data Communication

The former introductory notebook `00.5_Basics_of_a_Data_Communication_System.ipynb` was moved into this section. The current order is:

1. `02.1_Basics_of_Data_Communication.ipynb`
2. `02.2_Source_Coding.ipynb`
3. `02.3_Channel_Coding.ipynb`
4. `02.4_Digital_Modulation.ipynb`
5. `02.5_Multipath_and_OFDM.ipynb`
6. `02.6_Noise_and_Interference.ipynb`
7. `02.7_Path_Loss_of_Radio_Communication.ipynb`
8. `02.8_Radio_Spectrum.ipynb`
9. `02.9_Shannon_Capacity.ipynb`

Their internal headings were shifted to match the filenames. References were also updated in `02_Notebooks/README.md`, `03_Assignments/Assignment-01.md`, and `03_Assignments/Assignment-02.md`.

The two figures in `02.1_Basics_of_Data_Communication.ipynb` use centered HTML images with `max-width: 60%` and automatic height.

## Entropy notebook decisions

File: `02_Notebooks/01_Data_and_Signals/01.5_Entropy.ipynb`

- Section 5.1 is now an intuitive introduction. The duplicate entropy equation was removed from it.
- Section 5.2.2 is the formal location of the Shannon entropy equation and includes a link to Claude Shannon's Wikipedia biography.
- Section 5.2.2 explicitly defines **symbol entropy** as the entropy of one source symbol considered without previous, following, or neighboring symbols as context. Its unit is bit per source symbol.
- Section 5.3, “From Entropy to Bits for Communication,” relates entropy to transmitted bits. It uses 2-bit quantizer outputs (`00`, `01`, `10`, `11`) as source symbols and compares their uncompressed representations with probability-based codewords. The example shows 1.75 bit per source symbol versus 2 bit per source symbol.
- The hands-on exercise is now Section 5.4. It explicitly says that “entropy” in the questions means Shannon entropy.
- The coin questions define heads, tails, `P(H)`, and `P(T)=1-P(H)` before asking students to calculate entropy.
- A final question asks students to relate their calculated entropy values to the theoretical minimum average number of transmitted bits per symbol and explain fractional averages.
- `compute_entropy` checks whether probabilities sum to 1 using `math.isclose`. Invalid input prints a warning and returns the string `"undefined"`; it does not raise an exception.
- Do not call an intentionally invalid distribution in the function-definition cell, because that displays the warning as soon as the cell is run.
- Entropy output labels use `bit per coin toss` for coins and `bit per die roll` for dice.
- The code cell deliberately contains a student modification point inside the logarithm. Do not silently turn the exercise into a completed solution unless requested.

## Correlation notebook decisions

File: `02_Notebooks/01_Data_and_Signals/01.6_Correlation.ipynb`

This notebook was substantially revised on August 20, 2026. Preserve the user's manual edits and inspect the live notebook before making further changes.

- The notebook now follows the progression entropy -> correlation -> conditional entropy -> redundancy.
- Section 6.2 defines the Pearson correlation coefficient $\rho_{X,Y}$ and explains covariance and standard deviation with their finite-dataset formulas.
- The worked calculation uses `X=[1,2,3]` and `Y=[5,7,9]`, which are visually separated and have the exact relationship $Y=2X+3$, hence $\rho_{X,Y}=1$.
- Plotted correlation coefficients use four decimal places so a value such as `0.9959` is not misleadingly displayed as `1.00`.
- Section 6.2.4 shows three examples: positive linear, negative linear, and nonlinear $Y=X^2$. Each example includes the original paired data, an $x$-versus-$y$ scatter plot, and a rolling correlation over a 21-observation window.
- The text explicitly states that Pearson correlation measures linear dependence only. Independence implies zero correlation when correlation is defined, but zero correlation does not imply independence.
- The rolling-correlation discussion bridges to cross-correlation carefully: rolling correlation varies with position, while cross-correlation varies with lag. Do not describe them as the same operation.
- Section 6.3 reuses the same three example datasets to visualize cross-correlation over lag.
- Section 6.4 explains autocorrelation in connected prose, not bullet points.
- Section 6.5 connects correlation to conditional entropy using independent and alternating binary sources.
- The former Section 6.6 summary heading was removed, but its bridge text remains. Hands-On Exercise is now Section 6.6.
- Exercise questions are split into one markdown cell per question. They use one blank line followed by `(answer here)` and do not use `Answer:` labels.
- The first exercise asks for $\rho_{X_n,X_{n-1}}$ for an alternating source and an independent source. The next question uses conditional entropy to connect back to entropy.
- The cross-correlation table leaves only the $k=-1$ row completed. It contains `(answer here)` only once; the other student cells are blank.
- The implementation exercise deliberately contains `range(0,0)` as its modification point. Its check prints normal guidance rather than raising an assertion error.
- Use normal hyphens rather than em dashes throughout this notebook.

## Redundancy notebook decisions

File: `02_Notebooks/01_Data_and_Signals/01.7_Redundancy.ipynb`

This notebook was substantially revised on August 20-21, 2026.

- The old notebook treated redundancy almost entirely as deliberately added error-control bits. The revised notebook focuses on redundancy already present in source data.
- **Source redundancy** is predictable or repeated structure already present in data and may be removed by compression.
- **Channel-coding redundancy** is structured information added deliberately to detect or correct transmission errors. This material is now in `02.3_Channel_Coding.ipynb`.
- Section 7.1 bridges directly from correlation and conditional entropy. It compares independent fair bits with the alternating sequence `0 1 0 1 ...`.
- Section 7.2 introduces $I(X_n;X_{n-1})=H(X_n)-H(X_n\mid X_{n-1})$ as a measure of predictable information shared by successive symbols. It explains the distinction between self-information $I(E)$ and mutual information $I(X;Y)$.
- In the mutual-information example, $a$ denotes the previous symbol and $b$ the current symbol. The text defines $p(b)$, $p(a,b)$, and $p(b\mid a)$ explicitly.
- Mutual information is expressed in bit per adjacent symbol pair. For the binary examples its range is 0 to 1 bit per adjacent symbol pair; the general upper bound is $\min\{H(X_n),H(X_{n-1})\}$.
- The worked examples use $I_A=0$ for the independent source and $I_B=1$ for the alternating source.
- The mutual-information comparison is shown using `../../.admin/img/mutual_information.svg` rather than a generated notebook plot.
- Section 7.3, “Redundancy in Symbol Encoding,” uses a 2-bit encoding with entropy 1.5 bit per symbol, giving 0.5 bit per symbol or 25% relative redundancy.
- Section 7.3 explicitly calls $L-H$ the number of **excess bits** used per symbol on average.
- Section 7.4 bridges directly into the Source Coding notebook. Hands-On Exercise is Section 7.5.
- Exercise questions are split into individual cells and use one blank line followed by `(answer here)` without `Answer:` labels.
- All malformed LaTeX `\text{...}` escapes were corrected.

## Channel Coding notebook decisions

File: `02_Notebooks/02_Data_Communication/02.3_Channel_Coding.ipynb`

- Channel-coding material formerly in Redundancy Sections 7.3-7.4.2 was moved here so the Data and Signals sequence remains focused on source redundancy.
- The notebook distinguishes source redundancy from deliberately added channel-coding redundancy, defines code rate, and uses repetition coding and majority decoding as the first example.
- It includes the majority-decoding error probability, the reliability-versus-rate visualization, and a short bridge to Digital Modulation.
- The communication chain is `source data -> source coding -> channel coding -> digital modulation -> channel`.
- The binomial coefficient is explained using $\binom{m}{i}=m!/[i!(m-i)!]$, the factorial definition, $0!=1$, and the example $\binom{3}{2}=3$.
- The visualization explanation states that increasing odd $m$ improves reliability for $p<0.5$ while lowering the code rate $R=1/m$.
- Error detection and error correction are distinguished explicitly. CRC is presented as error detection, while repetition and Hamming codes illustrate correction.
- Related written questions and repetition encoder/decoder exercises were moved with the explanation. Questions remain one per cell with one blank line before `(answer here)`.
- Incomplete code exercises use safe placeholders and readable feedback rather than assertion tracebacks.
- Use normal hyphens rather than em dashes throughout this notebook.

## Source Coding notebook decisions

File: `02_Notebooks/02_Data_Communication/02.2_Source_Coding.ipynb`

- This notebook was moved from Data and Signals, renamed from Data Compression to Source Coding, and renumbered from 8.x to 2.x.
- Section 2.1 defines source coding first and presents data compression as the resulting reduction in encoded size. It introduces lossless and lossy source coding and explains the mobile-computing constraints that motivate them.
- Section 2.1.1 compares separate ZIP files for independent and alternating binary sources. The generated files are kept in `02_Data_Communication/compression_example_files`.
- Section 2.2 is an interactive character-entropy example. It states that the calculator measures symbol frequencies but does not capture order or sequential predictability.
- Section 2.3 introduces Huffman coding and qualifies that equal single-symbol frequencies do not prove a complete source is incompressible.
- Section 2.4 compares the cat image at JPEG qualities 100, 80, 60, 40, 20, and 3 in a two-row grid.
- Section 2.5 summarizes source-coding trade-offs without repeating the introduction. Section 2.6 bridges to Channel Coding. Hands-On Exercise is Section 2.7.
- Exercise questions are split into individual cells. The text-entropy exercises ask for examples near 0 and 1 bit per character and a maximum-entropy string of exactly ten letters.

## Digital Modulation notebook decisions

File: `02_Notebooks/02_Data_Communication/02.4_Digital_Modulation.ipynb`

- Section 4.1 bridges from channel-coded bits to modulation symbols and physical waveforms. It distinguishes baseband links from wireless and other passband systems.
- The ASK exercise deliberately uses the safe incomplete line `amp = 0`; do not complete it unless requested.
- ASK, FSK, BPSK, QAM constellations, Gray mapping, time-domain QAM, symbol rate, noisy constellations, and adaptive modulation are included.
- `qam_points` normalizes every constellation to unit average power. This normalization is required by the $E_s/N_0$ noise example and the comparison between modulation orders.
- QPSK and square 4-QAM are described as equivalent up to rotation and scaling, not simply identical names.
- Section 4.3.4 distinguishes modulation bit rate $R_b=R_s\log_2(M)$ from net information rate $R_{\text{information}}=R_cR_s\log_2(M)$.
- The QAM time-domain example uses cycles per symbol and a time axis measured in symbol periods, not an inconsistent hertz label.
- Exercise questions are split into individual cells without `Answer:` labels. The 5G question refers to channel quality or SINR rather than distance or signal strength alone.

## 05 Mobile AI sequence prepared for discussion

The Mobile AI folder was reorganized on August 26 into a proposed numbered sequence of 19 notebooks:

1. `05.1_Introduction_to_LLMs.ipynb`
2. `05.2_Introduction_to_Local_LLMs.ipynb`
3. `05.3_GettingStarted_with_Raspberry_Pi.ipynb`
4. `05.4_Understanding_Tokenization.ipynb`
5. `05.5_Understanding_Word_Embedding.ipynb`
6. `05.6_Understanding_Attention.ipynb`
7. `05.7_Understanding_Training.ipynb`
8. `05.8_Understanding_Inference_Control.ipynb`
9. `05.9_Understanding_Reasoning_Models.ipynb`
10. `05.10_Understanding_Chain_of_Thought_Reasoning.ipynb`
11. `05.11_Experimenting_with_Prompts.ipynb`
12. `05.12_Local_Agents.ipynb`
13. `05.13_Local_RAG.ipynb`
14. `05.14_Local_Model_Context_Protocol.ipynb`
15. `05.15_Making_Models_Smaller.ipynb`
16. `05.16_GRAND_FINALE_The_2026_Tuning_Competition.ipynb`
17. `05.17_Build_Your_Own_MicroLLM_STEP1-Initialization.ipynb`
18. `05.18_Build_Your_Own_MicroLLM_STEP2-Training.ipynb`
19. `05.19_Build_Your_Own_MicroLLM_STEP3-Performance_Test.ipynb`

- The former `HandsOn_` filenames were removed in favor of chapter-numbered filenames. Do not restore the old names without revisiting the proposed sequence.
- The former LLM architecture material is included in `05.2_Introduction_to_Local_LLMs.ipynb` rather than retained as a separate notebook.
- `05.6_Understanding_Attention.ipynb` combines the former overview and detailed attention material.
- `05.7_Understanding_Training.ipynb` replaces the former language-model training and inference notebook in the proposed sequence.
- `05.4`, `05.9`, and `05.12` through `05.15` are title-only placeholder notebooks. They require content before the sequence is ready for teaching.
- `02_Notebooks/README.md` now lists the proposed sequence. Assignment 02 and Assignment 03 references were updated to the numbered filenames; Assignment 03 notes that the former optional hardware-architecture material is included in `05.2`.
- `02_Notebooks/05_Mobile_AI/marcel.md` is a discussion and comparison note. It records the proposed sequence and compares the notebook inventories on `origin/dev05-06` and `dev2026`; it is not a student-facing course notebook.
- This restructuring was committed as preparation for discussion, not as a completed editorial review. Inspect notebook titles, internal section numbers, exercise formatting, links, and pedagogical scope before treating the sequence as final.

## 06 Cloud Computing sequence

The Cloud Computing sequence was normalized on August 25:

1. `02_Notebooks/06_Cloud_Computing/06.1_Cloud_Computing.ipynb`
2. `02_Notebooks/06_Cloud_Computing/06.2_Cloud_Providers_and_Availability.ipynb`
3. `02_Notebooks/06_Cloud_Computing/06.3_Build_Your_Own_Cloud.ipynb`

- Do not restore the former `HandsOn_` filename prefixes or the “Hands-On Exercise” wording in the main notebook titles.
- Each notebook uses the standard `06 Cloud Computing` chapter header, followed by the numbered title `1`, `2` or `3`. Internal headings and prose section references were renumbered consistently.
- Exercise blue boxes use the exact standard submission text documented below.
- Every numbered Cloud exercise question is one bold paragraph beginning with `Question NN:`. The number is not a separate heading. The next paragraph is `(answer here)` without `Answer:` or bullet placeholders.
- The optional feedback prompt uses the shared teaching-team wording.
- `06.1_Cloud_Computing.ipynb` imports `cloud_simulation` directly. Its module is `02_Notebooks/06_Cloud_Computing/cloud_simulation.py`; do not recreate the former `misc` package.
- Six Cloud SVGs live in `.admin/img/`, named `02_cloud_definition_views.svg` through `07_secure_api_request.svg`. Their matching generator scripts are beside them with identical stems and a `.py` extension.
- The SVGs inherit `Arial, Helvetica, sans-serif` from the root element and have transparent outer canvases. Their internal white cards, colored panels, borders and arrows remain opaque. Each generator uses `Path(__file__).with_suffix(".svg")` and must preserve these font/background decisions.

## Standard exercise submission box

All 50 top-level course notebooks with exercise or question sections use exactly:

```html
<div class="alert alert-block alert-info">Fill in your responses and save this notebook. See the <a href="../../03_Assignments/Submission-Guidelines.md">submission guidelines</a> for how to submit your work.</div>
```

Special notes such as “not graded,” run-specific evidence requirements, and tournament instructions remain immediately above the standardized box. The five archival notebooks under `02_Data_Communication/audio` are excluded because their directory depth requires a different relative link.

## Getting Started title/logo

File: `02_Notebooks/00_Intro/00.1_Check_Course_Environment.ipynb`

The ETH logo remains above the centered title. Its paragraph has zero margin and zero line height to reduce the gap, while the title keeps its default top margin. A responsive same-line title/logo layout was attempted and reverted because it did not render reliably in the target notebook environment.

## Next editorial task

Entropy, Correlation, Redundancy, Source Coding, Channel Coding, and Digital Modulation have now been revised. The next notebook in sequence is `02.5_Multipath_and_OFDM.ipynb`. Inspect the live file and current uncommitted work before editing it.

The recommended next progression is:

1. Review Multipath and OFDM for conceptual accuracy and a clear bridge from Digital Modulation.
2. Continue through Noise and Interference, Path Loss, Radio Spectrum, and Shannon Capacity in sequence.
3. Preserve the established style: connected prose where possible, precise notation, one question per exercise cell, readable feedback instead of assertion tracebacks, and normal hyphens rather than em dashes.

Preserve the current uncommitted notebook moves, editorial changes, generated example files, and `.admin/AGENTS.md` updates shown by `git status`.

Do not discard or overwrite existing work. Notebook editors may retain stale in-memory copies; inspect the file on disk before editing and ask the user to reload rather than saving an older open copy over the repository version.

## Deferred LLM connection

Later, discuss whether entropy, correlation, redundancy, and compression can be connected meaningfully to **tokenization** to introduce a small amount of LLM context. The connection should support the existing learning progression rather than becoming a separate LLM lesson. Possible themes include text converted into tokens as source symbols, nonuniform token frequencies, predictable token sequences, redundancy in language, and the distinction between token count and encoded bit count. This is a discussion item, not yet an approved notebook change.

Current recommendation for that discussion: add a short “Modern connection: tokenization and LLMs” callout near the end of the Source Coding notebook, possibly with an optional exercise comparing one sentence as characters, UTF-8 bytes, and tokenizer tokens. Explain that tokenization can replace frequent character sequences with reusable symbols, while an LLM uses preceding tokens to predict the next token and is evaluated using cross-entropy. Preserve the key caveats: tokenization is not itself optimal bit-level compression, token IDs still require binary encoding, fewer tokens do not automatically mean proportionally fewer bits, and LLM tokenizers are designed for model usefulness as well as representation efficiency.
