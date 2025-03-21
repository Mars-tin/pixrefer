# PixRefer

## Precommit Setup
We use Google docstring format for our docstrings and the pre-commit library to check our code. To install pre-commit, run the following command:

```bash
conda install pre-commit  # or pip install pre-commit
pre-commit install
```

The pre-commit hooks will run automatically when you try to commit changes to the repository.



## Quickstart
**These tasks require a GUI, so it is recommended that you run it on a Mac / Windows.
### Clone git repo
```bash
git clone https://github.com/Mars-tin/pixrefer.git
cd pixrefer
pip install -e .
```

### Install some packages
If you are using a Mac, run the following code to install PyAudio:
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
Please replace the key with the real api key provided.

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

For each image, you are required to click where you think the **unique** object in the red box (you cannot see it) is located. 
![rel_regular](asset/rel_regular.gif)

If you find multiple objects that match the description, click `Multiple Match` and confirm your guess.
![rel_multiple_match](asset/rel_multiple_match.gif)

If you cannot find such an object in the image, click `Cannot Tell Where The Object Is` and confirm your guess.
![rel_nomatch](asset/rel_nomatch.gif)

You can always use `Enter(Return)` on your keyboard to quickly confirm and go to the next image.


#### REG task
```bash
bash pixrefer/interface/run_reg.sh
```

For each image, you are required to give **at least one** description of the object in the red box to make it can be **uniquely identified** by another person.

Write a text description:
![reg_text](asset/reg_text.gif)
After you finish, please click `Save Description` to save your result and you will see a green 'Text ✓'.

Record an audio description:
*Please note that you need to set the google api key in the `.env` file to proceed.*
![reg_audio](asset/reg_audio.gif)

Click `Audio` to switch to the audio mode, and click `Start Recording` to record. When you finish, click `Stop Recording`. You can edit the translation words, and click `Save Description` to save the edited result.

You can always use `Enter(Return)` on your keyboard to quickly confirm and go to the next image.