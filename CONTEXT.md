# Leynor

A private workspace that takes one idea to a rendered 9:16 Reel. The language below is what the code and the interface call things.

## Language

**Organization**:
The tenant. Everything a person sees is scoped to one.
_Avoid_: Account, team, workspace

**Brand**:
The client a project works for, owned by the organization. Several projects can answer one brand.
_Avoid_: Client (in code), company

**Audience**:
One group of people a brand makes work for, described once on that brand. Not a persona and not a list of followers.
_Avoid_: Target, segment, ICP (in code)

**ICP**:
Ideal customer profile: the strategic definition of who a brand should reach. It is what an audience records; the word does not appear in the model.
_Avoid_: Persona

**Project**:
The workspace a brand's work is delivered in. Holds campaigns, nothing else.
_Avoid_: Folder, board

**Campaign**:
One brief inside a project: a title, a default goal, and one audience to speak to. It knows no channel.
_Avoid_: Post, content, draft

**Brief**:
The instruction a campaign carries and its output units answer. The campaign row is the brief.

**Output unit**:
One piece a channel produces for a campaign. A Reel is Instagram's unit. Shares a title, a prompt and a goal across channels.
_Avoid_: Content piece, asset, item

**Prompt**:
What one output unit must say, in the operator's words. Not the model prompt that ships with a step.
_Avoid_: Instructions, description

**Goal** (on an output unit):
The one outcome a piece chases: saves, shares or follows. It cannot be inherited.
_Avoid_: Objective, KPI, target

**Campaign goal**:
What a campaign must achieve, in the operator's words. Written as prose, and never the same field as a unit's goal.
_Avoid_: Aim, objective

**Reel**:
Instagram's output unit: a 9:16 video, 60 to 180 seconds, with a six-step route.
_Avoid_: Video, clip, short

**Route**:
The fixed six steps a Reel passes: Spark, Hook, Board, Look, Voice, Print.
_Avoid_: Pipeline, flow, stage list

**Gate**:
One decision on one step of a route, recorded as a row. Exactly one per reel and step.
_Avoid_: Checkpoint, approval, status

**Render**:
The mp4 a route produces, plus the artifacts behind it, stored by key.
_Avoid_: Export, output file

**Publication**:
One posted instance of a unit on one channel account, with its external id and stats.
_Avoid_: Post (as a noun for this), upload
