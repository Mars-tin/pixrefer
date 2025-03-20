# PixRefer

## Precommit Setup
We use Google docstring format for our docstrings and the pre-commit library to check our code. To install pre-commit, run the following command:

```bash
conda install pre-commit  # or pip install pre-commit
pre-commit install
```

The pre-commit hooks will run automatically when you try to commit changes to the repository.



## Quickstart
### Clone git repo
```bash
git clone https://github.com/Mars-tin/pixrefer.git
cd pixrefer
pip install -e .
```

### Download the data
```bash
git lfs install
git clone https://huggingface.co/datasets/Seed42Lab/Pixrefer_data
```
### Prepare the google key

Create empty .env file:
```bash
touch .env
```
And add the content below: 
`GOOGLE_API_KEY={YOUR_API_KEY}`

### Launch the demo
#### REL task
```bash
bash pixrefer/interface/run_rel.sh
```
**Please note you need to change the JSON file path in this file first**: [run_rel.sh](pixrefer/interface/run_rel.sh)

Replace the following path with your given data:
```bash
--json_path Pixrefer_data/data/rel_user_input/gpt4o_concise_results.json
```

#### REG task
```bash
bash pixrefer/interface/run_reg.sh
```
