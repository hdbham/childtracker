import json

# Load your downloaded service account json
with open(".streamlit/Polksdc Firebase Admin SDK.json", "r") as f:
    data = json.load(f)

# Open a file to write properly formatted toml
with open(".streamlit/secrets2.toml", "w") as f:
    f.write("[firebase]\n")

    for key, value in data.items():
        if key == "private_key":
            # handle multiline private key properly
            f.write(f'{key} = """{value}"""\n')
        else:
            # write regular keys safely
            if isinstance(value, str):
                value = value.replace('"', '\\"')  # escape double quotes if any
                f.write(f'{key} = "{value}"\n')
            else:
                f.write(f"{key} = {value}\n")

print("✅ secrets.toml generated successfully!")
