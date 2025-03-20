# PixRefer

## Precommit Setup
We use Google docstring format for our docstrings and the pre-commit library to check our code. To install pre-commit, run the following command:

```bash
conda install pre-commit  # or pip install pre-commit
pre-commit install
```

The pre-commit hooks will run automatically when you try to commit changes to the repository.



## Quickstart

```bash
git clone https://github.com/Mars-tin/pixrefer.git
cd pixrefer
pip install -e .
```

## Launch the demo
REG task:
```bash
bash pixrefer/interface/run_reg.sh
```

REL task:
```bash
bash pixrefer/interface/run_rel.sh
```