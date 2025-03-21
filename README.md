# PixRefer

## Precommit Setup
We use Google docstring format for our docstrings and the pre-commit library to check our code. To install pre-commit, run the following command:

```bash
conda install pre-commit  # or pip install pre-commit
pre-commit install
```

The pre-commit hooks will run automatically when you try to commit changes to the repository.



## Quickstart
**This task requires a GUI, so it is recommended that you run it on a Mac.
### Clone git repo
```bash
git clone https://github.com/Mars-tin/pixrefer.git
cd pixrefer
pip install -e .
```

### Install some packages
Run the following code to install PyAudio on Mac:
```bash
brew install portaudio
pip install pyaudio
```

Run the following code to install google-cloud-speech:
```bash
pip install google-cloud-speech
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

Replace the following path with your given data path. For example, you may need to annotate the `llava_7b_concise_results.json`:
```bash
--json_path Pixrefer_data/data/rel_user_input/llava_7b_concise_results.json  # replace the example gpt_4o file path here
```

For each image, you are require to click where you think the object in the red box (you cannot see it) is located. 
- If you find the multiple objects matches the description, click `Multiple Match` and confirm your guess.
- If you cannot find such an object in the image, click `Cannot Tell Where The Object Is` and confirm your guess.

You can always use `Enter(Return)` on your keyboard to quickly confirm and go to the next image.


#### REG task
```bash
bash pixrefer/interface/run_reg.sh
```
