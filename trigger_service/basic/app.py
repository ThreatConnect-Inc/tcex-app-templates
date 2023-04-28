"""ThreatConnect Trigger Service App"""
# standard library
from typing import cast

# third-party
from tcex.app.playbook import Playbook
from tcex.app.service import CommonServiceTrigger

# first-party
from app_inputs import TriggerConfigModel
from service_app import ServiceApp  # Import default Service App Class (Required)


class App(ServiceApp):
    """Service App Template."""

    def run(self) -> None:
        """Run the trigger logic."""
        service: CommonServiceTrigger = cast(CommonServiceTrigger, self.tcex.app.service)

        while service.loop_forever(sleep=30):
            # startup inputs, access via self.inputs.model.service_input
            self.log.debug(f'Server configuration service_input {self.tcex.inputs.model.dict()}')

            # any "extra" args passed to fire_event will be
            # available in kwargs in the callback method
            service.fire_event(self.trigger_callback, my_data='data')

    # pylint: disable=unused-argument
    def trigger_callback(
        self, playbook: Playbook, trigger_id: int, config: TriggerConfigModel, **kwargs
    ) -> bool:
        """Execute trigger callback for all current configs.

        Args:
            playbook: An instance of Playbooks used to write output
                variables to be used in downstream Apps.
            trigger_id: The ID of the Playbook Trigger.
            config: The trigger input configuration data.
            **kwargs: Any additional arguments passed to the callback via the fire_event method.

        Returns:
            bool: True if playbook should trigger, False if not.
        """
        # "extra" args passed to the fire_event method are available in kwargs
        my_data: str | None = kwargs.get('my_data')

        self.log.debug(f'my_data: {my_data}')

        # args defined in install.json with serviceConfig set to False are available in config
        self.log.debug(f'''Playbook configuration playbook_input {config.playbook_input}''')

        # write output variable
        playbook.create.variable('example.service_input', self.in_.service_input)
        playbook.create.variable('example.playbook_input', config.playbook_input)
        return True
