from bisect import bisect_right

from termcolor import cprint

from dataClasses.base import Recipe, IngredientCollection, Ingredient


coil_multipliers = {
    'cupronickel': 0.5,
    'kanthal': 1.0,
    'nichrome': 1.5,
    'tungstensteel': 2.0,
    'HSSG': 2.5,
    'HSSS': 3.0,
    'naquadah': 3.5,
    'naquadah alloy': 4,
    'trinium': 4.5,
    'electrum flux': 5,
    'awakened draconium': 5.5,
}
coil_heat = {
    'cupronickel': 1801,
    'kanthal': 2701,
    'nichrome': 3601,
    'tungstensteel': 4501,
    'HSSG': 5401,
    'HSSS': 6301,
    'naquadah': 7201,
    'naquadah alloy': 8101,
    'trinium': 9001,
    'electrum flux': 9901,
    'awakened draconium': 10801,
}

# chem plant stuff
pipe_casings = {
    'bronze': 2,
    'steel': 4,
    'titanium': 6,
    'tungstensteel': 8
}

# [speed X, EU/t discount, parallels per tier]
GTpp_stats = {
    # In order of search query:
    # machine type.*\[gt\+\+\]
    'industrial centrifuge': [1.25, 0.9, 6],
    'industrial material press': [5.0, 1.0, 4],
    'industrial electrolyzer': [1.8, 0.9, 2],
    'maceration stack': [0.6, 1.0, 8],
    'wire factory': [2.0, 0.75, 4],

    'industrial mixing machine': [2.5, 1.0, 8],
    'industrial mixer': [2.5, 1.0, 8],

    'industrial sifter': [4, 0.75, 4],

    'large thermal refinery': [1.5, 0.8, 8],
    'industrial thermal centrifuge': [1.5, 0.8, 8],

    'industrial wash plant': [4.0, 1.0, 4],
    'industrial extrusion machine': [2.5, 1.0, 4],

    'large processing factory': [2.5, 0.8, 2],
    'LPF': [2.5, 0.8, 2],

    'high current industrial arc furnace': [2.5, 1.0, 8],
    'industrial arc furnace': [2.5, 1.0, 8],

    'large scale auto-assembler': [2.0, 1.0, 2],
    'cutting factory controller': [2.0, 0.75, 4],

    'boldarnator': [2.0, 0.75, 8],
    'industrial rock breaker': [2.0, 0.75, 8],

    'dangote - distillery': [0, 1.0, 48]
}

voltage_cutoffs = [33, 129, 513, 2049, 8193, 32769, 131_073, 524_289, 2_097_153]
voltages = ['LV', 'MV', 'HV', 'EV', 'IV', 'LuV', 'ZPM', 'UV', 'UHV']


def require(recipe, requirements):
    # requirements should be a list of [key, type]
    for req in requirements:
        key, req_type = req
        pass_conditions = [key in vars(recipe), isinstance(getattr(recipe, key), req_type)]
        if not all(pass_conditions):
            raise RuntimeError(f'Improper config! Ensure {recipe.machine} has key {key} of type {req_type}.')


def modifyGTpp(recipe):
    if recipe.machine not in GTpp_stats:
        raise RuntimeError('Missing OC data for GT++ multi - add to gtnhClasses/overclocks.py:GTpp_stats')

    SPEED_BOOST, EU_DISCOUNT, PARALLELS_PER_TIER = GTpp_stats[recipe.machine]
    SPEED_BOOST = 1/(SPEED_BOOST+1)

    available_eut = voltage_cutoffs[voltages.index(recipe.user_voltage)]
    MAX_PARALLEL = (voltages.index(recipe.user_voltage) + 1) * PARALLELS_PER_TIER
    NEW_RECIPE_TIME = max(recipe.dur * SPEED_BOOST, 20)

    x = recipe.eut * EU_DISCOUNT
    y = min(int(available_eut/x), MAX_PARALLEL)
    TOTAL_EUT = x*y

    cprint('Base GT++ OC stats:', 'yellow')
    cprint(f'{available_eut=} {MAX_PARALLEL=} {NEW_RECIPE_TIME=} {TOTAL_EUT=} {y=}', 'yellow')

    while TOTAL_EUT < available_eut:
        OC_EUT = TOTAL_EUT * 4
        OC_DUR = NEW_RECIPE_TIME / 2
        if OC_EUT <= available_eut:
            if OC_DUR < 20:
                break
            cprint('OC to', 'yellow')
            cprint(f'{OC_EUT=} {OC_DUR=}', 'yellow')
            TOTAL_EUT = OC_EUT
            NEW_RECIPE_TIME = OC_DUR
        else:
            break

    recipe.eut = TOTAL_EUT
    recipe.dur = NEW_RECIPE_TIME
    recipe.I *= y
    recipe.O *= y

    return recipe


def modifyGTppSetParallel(recipe, MAX_PARALLEL, speed_per_tier=1):
    available_eut = voltage_cutoffs[voltages.index(recipe.user_voltage)]

    x = recipe.eut
    y = min(int(available_eut/x), MAX_PARALLEL)
    TOTAL_EUT = x*y
    NEW_RECIPE_TIME = round(recipe.dur * (speed_per_tier)**(voltages.index(recipe.user_voltage) + 1), 2)

    cprint('Base GT++ OC stats:', 'yellow')
    cprint(f'{available_eut=} {MAX_PARALLEL=} {NEW_RECIPE_TIME=} {TOTAL_EUT=} {y=}', 'yellow')

    while TOTAL_EUT < available_eut:
        OC_EUT = TOTAL_EUT * 4
        OC_DUR = NEW_RECIPE_TIME / 2
        if OC_EUT <= available_eut:
            if OC_DUR < 20:
                break
            cprint('OC to', 'yellow')
            cprint(f'{OC_EUT=} {OC_DUR=}', 'yellow')
            TOTAL_EUT = OC_EUT
            NEW_RECIPE_TIME = OC_DUR
        else:
            break

    recipe.eut = TOTAL_EUT
    recipe.dur = NEW_RECIPE_TIME
    recipe.I *= y
    recipe.O *= y

    return recipe


def modifyChemPlant(recipe):
    raise NotImplementedError()


def modifyZhuhai(recipe):
    recipe = modifyStandard(recipe)
    parallel_count = (voltages.index(recipe.user_voltage) + 2)*2
    recipe.O *= parallel_count
    return recipe


def modifyEBF(recipe):
    require(
        recipe,
        [
            ['coils', str],
            ['heat', int],
        ]
    )
    ebf_voltage_cutoffs = [x*4 for x in voltage_cutoffs]
    base_voltage = bisect_right(ebf_voltage_cutoffs, recipe.eut)
    user_voltage = voltages.index(recipe.user_voltage)
    oc_count = user_voltage - base_voltage

    actual_heat = coil_heat[recipe.coils] + 100 * min(0, user_voltage - 1)
    excess_heat = actual_heat - recipe.heat
    eut_discount = 0.95 ** (excess_heat // 900)
    perfect_ocs = (excess_heat // 1800)

    recipe.eut = recipe.eut * 4**oc_count * eut_discount
    recipe.dur = recipe.dur / 2**oc_count / 2**max(min(perfect_ocs, oc_count), 0)

    return recipe


def modifyPyrolyse(recipe):
    require(
        recipe,
        [
            ['coils', str]
        ]
    )
    oc_count = calculateStandardOC(recipe)
    recipe.eut = recipe.eut * 4**oc_count
    recipe.dur = recipe.dur / 2**oc_count / coil_multipliers[recipe.coils]
    return recipe


def calculateStandardOC(recipe):
    base_voltage = bisect_right(voltage_cutoffs, recipe.eut)
    user_voltage = voltages.index(recipe.user_voltage)
    oc_count = user_voltage - base_voltage
    if oc_count < 0:
        raise RuntimeError(f'Recipe has negative overclock! Min voltage is {base_voltage}, given OC voltage is {user_voltage}.\n{recipe}')
    return oc_count


def modifyStandard(recipe):
    oc_count = calculateStandardOC(recipe)
    recipe.eut = recipe.eut * 4**oc_count
    recipe.dur = recipe.dur / 2**oc_count
    return recipe


def modifyPerfect(recipe):
    oc_count = calculateStandardOC(recipe)
    recipe.eut = recipe.eut * 4**oc_count
    recipe.dur = recipe.dur / 4**oc_count
    return recipe


def overclockRecipe(recipe):
    ### Modifies recipe according to overclocks
    # By the time that the recipe arrives here, it should have a "user_voltage" argument which indicates
    # what the user is actually providing.
    machine_overrides = {
        # GT multis
        'pyrolyse oven': modifyPyrolyse,
        'large chemical reactor': modifyPerfect,
        'LCR': modifyPerfect,
        'electric blast furnace': modifyEBF,
        'EBF': modifyEBF,
        'blast furnace': modifyEBF,

        # Basic GT++ multis
        'industrial centrifuge': modifyGTpp,
        'industrial material press': modifyGTpp,
        'industrial electrolyzer': modifyGTpp,
        'maceration stack': modifyGTpp,
        'wire factory': modifyGTpp,
        'industrial mixing machine': modifyGTpp,
        'industrial mixer': modifyGTpp,
        'industrial sifter': modifyGTpp,
        'large thermal refinery': modifyGTpp,
        'industrial thermal centrifuge': modifyGTpp,
        'industrial wash plant': modifyGTpp,
        'industrial extrusion machine': modifyGTpp,
        'large processing factory': modifyGTpp,
        'LPF': modifyGTpp,
        'high current industrial arc furnace': modifyGTpp,
        'industrial arc furnace': modifyGTpp,
        'large scale auto-assembler': modifyGTpp,
        'cutting factory controller': modifyGTpp,
        'boldarnator': modifyGTpp,
        'industrial rock breaker': modifyGTpp,
        'dangote - distillery': modifyGTpp,

        # Special GT++ multis
        'industrial coke oven': lambda recipe: modifyGTppSetParallel(recipe, 24, speed_per_tier=0.96),
        'ICO': lambda recipe: modifyGTppSetParallel(recipe, 24, speed_per_tier=0.96),
        'dangote - distillation tower': lambda recipe: modifyGTppSetParallel(recipe, 12),
        'chem plant': modifyChemPlant,
        'chemical plant': modifyChemPlant,
        'exxonmobil': modifyChemPlant,
        'zhuhai': modifyZhuhai,
    }
    if recipe.machine in machine_overrides:
        return machine_overrides[recipe.machine](recipe)
    else:
        return modifyStandard(recipe)
