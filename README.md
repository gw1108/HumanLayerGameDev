# HumanLayerGameDev
Copy of HumanLayer skills Research/Plan/Implement. Now updated to be more Unity prototype gamedev specific. And also, incorporate Refine-Questions/Research/Design/Plan/Implement.

# How to use

If you have claude code simply copy and paste the .claude + thoughts folder. If you want the pipeline.py as well copy the hack folder and any files that are needed from there (should just be pipeline.py). If you don't like the folder structure, ask the LLM to move stuff around and fix the scripts.

## Example Adaptation Prompt

```
Carefully examine the refine-research-question, research-codebase,
research-codebase-skip, iterate-research-codebase, implement_plan,
create_design commands under .claude/commands. They might not be perfect
fits for our repository. They might have incorrect project folder
structure. They might also be unity/C# specific instead of using the
technology stack this project is using. Update and fix any issues you see.
```

# What pipeline.py does

Chains `refine → research → design → plan → implement` by launching `claude` per stage and feeding each stage's tagged output into the next. See [hack/README.md](hack/README.md) for details.
