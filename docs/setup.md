# Before the Lab: Software and Setup

Complete this setup before the first lab. You will edit the model configuration, process
your own measurements, run the simulation, and inspect the Notebook. Allow time for the
environment download; it should not be left until the 30-minute hands-on session.

## 1. Install the tools

1. Install [Miniforge](https://conda-forge.org/download/) for your operating system and
   processor. On macOS, choose **Apple Silicon (arm64)** or **Intel (x86_64)** to match
   your Mac. Windows users can open **Miniforge Prompt** from the Start menu; macOS and
   Linux users can use their terminal. An existing working Conda installation is also
   sufficient.
2. Install [Visual Studio Code](https://code.visualstudio.com/download) as the recommended
   editor. In its Extensions view, install **Python** and **Jupyter** by Microsoft. An
   editor you already know is fine if it can edit Python and CSV files and run the Notebook.
3. Obtain the repository with Git, or use **Code → Download ZIP** on the
   [project page](https://github.com/chenzhang0920/devsim-silicon-solar-cell-teaching).
   If using ZIP, extract it before running any command. Git is useful for receiving later
   course updates, but is not needed to run the model.

## 2. Create the project environment

Open Miniforge Prompt or a terminal and go to the extracted project folder. If you use
Git, these two commands obtain it first:

```text
git clone https://github.com/chenzhang0920/devsim-silicon-solar-cell-teaching.git
cd devsim-silicon-solar-cell-teaching
```

Run the following commands **from the folder containing `environment.yml`**:

```text
conda env create -f environment.yml
conda activate devsim_solar
python -c "import devsim; print('DEVSIM:', devsim.__version__)"
python scripts/run_all.py full --dry-run
```

The first command creates the environment once. In a later terminal session, run
`conda activate devsim_solar` again; do not recreate the environment every time.
The DEVSIM check should print version **2.10.1**. The dry run should list the planned
steps without changing results.

## 3. Open the project in VS Code

1. Choose **File → Open Folder** and select the project folder, not just `config.py`.
2. Open `config.py`. Use **Python: Select Interpreter** in the Command Palette and select
   the Python interpreter from the `devsim_solar` Conda environment.
3. Open `notebooks/tutorial.ipynb`. Use **Select Kernel** at the upper right and choose
   the `devsim_solar` Python environment. The Notebook kernel and the editor interpreter
   may need to be selected separately.
4. Open a new VS Code terminal. Check that `python -c "import devsim"` succeeds before
   running any model command.

Alternatively, run `python -m jupyter lab notebooks/tutorial.ipynb` from an activated
terminal and use the browser Notebook. VS Code is recommended for editing; the model
does not depend on the editor.

## 4. Check the actual workflow

From the project folder with `devsim_solar` active, run:

```text
python scripts/run_all.py simulation
```

Open a generated figure in `results/` and locate the model settings in `config.py`.
For your own experiment, keep instrument exports in `data/raw/keithley/`, record the
illuminated area and polarity, and follow the
[Experiment Protocol](experiment_protocol.md) before processing or fitting data.
Edit only parameters you can justify from the device or measurement record. After editing
`config.py`, restart the Notebook kernel and rerun its cells so it uses the new values.

## If setup fails

- **`conda` is not recognized:** open Miniforge Prompt on Windows, or reopen the terminal
  after installing Miniforge on macOS/Linux.
- **`devsim` cannot be imported:** activate `devsim_solar` and check which Python is in
  use with `python -c "import sys; print(sys.executable)"`. The path should be inside the
  `devsim_solar` environment.
- **VS Code uses a different Python:** select the interpreter for `config.py` and the
  Notebook kernel separately, then open a new terminal.
- **Environment creation or DEVSIM installation fails:** keep the complete error message
  and tell the TA your operating system and processor type. Do not install a different
  DEVSIM version into the environment without checking compatibility.

Official references: [Miniforge installation](https://conda-forge.org/download/),
[Conda environment creation](https://docs.conda.io/projects/conda/en/stable/commands/env/create.html),
[VS Code Python environments](https://code.visualstudio.com/docs/python/environments), and
[VS Code Notebook kernels](https://code.visualstudio.com/docs/datascience/jupyter-notebooks).
