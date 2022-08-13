"""
Variables used for wireless access point imports.  These include transform
dictionaries, allowed channels, center frequencies, and anything else
required during AP model validation.

NOTE: Currently, definitions are in place for 2.4 and 5GHz channel assignments.
6GHz *might* be added in the future if needed and time permits!
"""

valid_channel_numbers_24ghz = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)
denied_channel_numbers_24ghz = (2, 3, 4, 5, 7, 8, 9, 10, 12, 13)

# Create the allowed channel numbers with a comprehension - generate a new
# tuple with the diff of the valid - denied channel numbers
allowed_channel_numbers_24ghz = tuple(
    x for x in valid_channel_numbers_24ghz if x not in denied_channel_numbers_24ghz
)


# Allowed 5GHz channel numbers by channel width
channel_range_5ghz_20mhz = (
    36, 38, 40, 42, 44, 46, 48, 50, 52, 54, 56,
    58, 60, 62, 64, 100, 102, 104, 106, 108, 110, 112,
    114, 116, 118, 120, 122, 124, 126, 128, 132, 134, 136,
    138, 140, 142, 151, 153, 155, 157, 159, 161, 163, 165
)

channel_range_5ghz_40mhz = (
    38, 46, 54, 62, 102, 110, 118, 126, 134, 142, 151, 159
)

channel_range_5ghz_80mhz = (42, 58, 106, 122, 138, 155)
channel_range_5ghz_160mhz = (50, 114)

# Create a new sorted tuple that combines all valid 5GHz channels
valid_channel_numbers_5ghz = sorted(channel_range_5ghz_20mhz +
                                    channel_range_5ghz_40mhz +
                                    channel_range_5ghz_80mhz +
                                    channel_range_5ghz_160mhz)

denied_channel_numbers_5ghz = (44, 167, 169, 171, 173, 175, 177)

# And a new comprehension to create the allowed channels with the diff of the
# valid - denied 5GHz channels
allowed_channel_numbers_5ghz = tuple(
    x for x in valid_channel_numbers_5ghz if x not in denied_channel_numbers_5ghz
)

# 5GHz channels can be 20, 40, 80, or 160MHz in width.  If the width is not
# specified, create a default width of 20MHz
allowed_channel_width_5ghz = (20, 40, 80, 160)
default_channel_width_5ghz = 20  # pylint: disable=invalid-name

# Nobody cares about 2.4GHz channel width :) - just set it
default_channel_width_24ghz = 22  # pylint: disable=invalid-name

# Translation map to arrive at the expected NetBox channel number. This is used
# for model validation where a lookup of channel_width returns a new dict where
# keys represent the channels associated with a translated channel.  For
# example, channel width 40 with desired channel 36 returns 38, which is valid
# for the NetBox rf_channel option.
#
# For 5GHz 20MHz channels or 2.4GHz 22MHz channels, no key is found so the
# model will just return the specified channel.
netbox_channel_width_translation = {
    # Note: for 20MHz 5GHz and 22MHz 2.4GHz channels, it's 1:1 as long as the
    # channel is valid.
    40: {
        (36, 38, 40): 38,
        (44, 46, 48): 46,
        (52, 54, 56): 54,
        (60, 62, 64): 62,
        (100, 102, 104): 102,
        (108, 110, 112): 110,
        (116, 118, 120): 118,
        (124, 126, 128): 126,
        (132, 134, 136): 134,
        (140, 142, 144): 142,
        (149, 151, 153): 151,
        (157, 159, 161): 159
    },
    80: {
        (36, 38, 40, 42, 44, 46, 48): 42,
        (52, 54, 56, 58, 60, 62, 64): 58,
        (100, 102, 104, 106, 108, 110, 112): 106,
        (116, 118, 120, 122, 124, 126, 128): 122,
        (132, 134, 136, 138, 140, 142, 144): 138,
        (149, 151, 153, 155, 157, 159, 161): 155
    },
    160: {
        (36, 38, 40, 42, 44, 46, 48, 50, 52, 54, 56, 58, 60, 62, 64): 50,
        (100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120, 122, 124, 126, 128): 114
    }
}

# And the reverse channel transformation.  If NetBox is assigned a channel
# corresponding to the UNII-x channel, get the expected channel number for
# the WLC - in this case, a Cisco 9800 series that expects the channel to be
# the first channel from the bonded width.
netbox_channel_to_cisco_wlc_translation = {
    # Cisco WLC expects the first 20MHz equivalent channel to be configured
    # for channel widths > 20MHz.
    38: 36,
    42: 36,
    46: 44,
    50: 36,
    54: 52,
    58: 52,
    62: 60,
    102: 100,
    106: 100,
    110: 108,
    114: 100,
    118: 116,
    122: 116,
    126: 124,
    134: 132,
    138: 132,
    142: 140,
    151: 149,
    155: 149,
    159: 157
}

# To complete the NetBox rf_channel creation, specify the center frequencies
# for each 2.4/5GHz channel.  Not used in practice, but we need this to
# create a valid NetBox mapping without defining a custom field.
channel_center_frequencies = {
    1: 2412.0,
    2: 2417.0,
    3: 2422.0,
    4: 2427.0,
    5: 2432.0,
    6: 2437.0,
    7: 2442.0,
    8: 2447.0,
    9: 2452.0,
    10: 2457.0,
    11: 2462.0,
    12: 2467.0,
    13: 2472.0,
    36: 5180.0,
    38: 5190.0,
    40: 5200.0,
    42: 5210.0,
    44: 5220.0,
    46: 5230.0,
    48: 5240.0,
    50: 5250.0,
    52: 5260.0,
    54: 5270.0,
    56: 5280.0,
    58: 5290.0,
    60: 5300.0,
    62: 5310.0,
    64: 5320.0,
    100: 5500.0,
    102: 5510.0,
    104: 5520.0,
    106: 5530.0,
    108: 5540.0,
    110: 5550.0,
    112: 5560.0,
    114: 5570.0,
    116: 5580.0,
    118: 5590.0,
    120: 5600.0,
    122: 5610.0,
    124: 5620.0,
    126: 5630.0,
    128: 5640.0,
    132: 5660.0,
    134: 5670.0,
    136: 5680.0,
    138: 5690.0,
    140: 5700.0,
    142: 5710.0,
    144: 5720.0,
    149: 5745.0,
    151: 5755.0,
    153: 5765.0,
    155: 5775.0,
    157: 5785.0,
    159: 5795.0,
    161: 5805.0,
    165: 5825.0,
}
