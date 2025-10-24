Testing Auto
===============================================================================
Current testing framework does not support TIE apps.  But tcex has a 'run' command that
takes in a json file of params.

But the tcex run command does not include the code around accessing secret keys in vault.

So I added the requirements.txt file under tests so when created deps folders, it would include
the deps_test which includes the testing module.

And then I wrote test_run_local.py to run this TIE app so I could grab the keys from vault.
Noticed that each test run will delete all the existing log files/data.

Command:
pyTest tests

Testing Manually
===============================================================================
Basically, the params are passed into the app for startup. For this TIE app, the command to
run from the root of the project:

tcex run --config-json tests/local-test-run.json

To clear out the log first and run:
rm -fr log/* | tcex run --config-json tests/local-test-run.json

And to run in debug mode for VSC:
rm -fr log/* | tcex run --debug --debug-port 5678 --config-json tests/local-test-run.json
