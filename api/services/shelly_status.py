"""Normalize Gen2+ Switch and permanently connected PM1 meter samples."""
from services.vpd_channels import finite_number


def parse_rpc_status(status):
    if not isinstance(status, dict) or status.get('error') is not None:
        return None
    def energy_total(component):
        energy = component.get('aenergy')
        return finite_number(energy.get('total')) if isinstance(energy, dict) else None

    switch = status.get('switch:0')
    if isinstance(switch, dict) and isinstance(switch.get('output'), bool):
        return {'isOn': switch['output'], 'Watt': finite_number(switch.get('apower')),
                'Wh': energy_total(switch),
                'meteringOnly': False}
    meter = status.get('pm1:0')
    if not isinstance(meter, dict) or type(meter.get('id')) is not int or meter['id'] != 0:
        return None
    power = finite_number(meter.get('apower'))
    energy = energy_total(meter)
    if power is None or energy is None or energy < 0:
        return None
    return {'isOn': True, 'Watt': power, 'Wh': energy, 'meteringOnly': True}
