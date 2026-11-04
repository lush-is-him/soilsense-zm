/**
 * SoilSense ZM: short follow-up form for the second agronomist (AGR-2).
 *
 * script.google.com > New project > paste > Save > choose createFollowUpForm > Run.
 * The Execution log prints the link to send and the responses spreadsheet.
 */

function createFollowUpForm() {
  var form = FormApp.create('SoilSense ZM: follow-up questions');
  form.setDescription(
    'Thank you again for your answers. A few of them need a short follow-up so the system gives the right ' +
    'amounts. About 10 minutes. Write "unsure" where that is the honest answer.');
  form.setCollectEmail(false);
  form.setProgressBar(true);
  form.setConfirmationMessage('Thank you! This completes the rule tables.');

  var groups = ['Sandy', 'Loamy', 'Clay', 'Not sure'];
  var num = FormApp.createTextValidation().requireNumber().setHelpText('Please enter a number').build();

  // ----- Part 1: soil texture groups -----
  form.addPageBreakItem().setTitle('Part 1 of 3: Soil texture for the lime table').setHelpText(
    'WHY WE ASK: the lime table you agreed to has only three columns: sandy, loamy and clay. ' +
    'But soil labs and the iSDAsoil map describe texture with 12 names (the USDA texture classes). ' +
    'The system must put each of the 12 into one of your three columns to pick the lime amount, ' +
    'and the choice can double or halve the lime.\n\n' +
    'In your first answer some names appeared in two groups and some were missing. ' +
    'Please choose ONE group for each of the 12 below, thinking of how much lime the soil needs. ' +
    'The description is how the soil feels when wet and rubbed between the fingers.');
  var classes = [
    ['Sand', 'loose and gritty; will not form a ball'],
    ['Loamy sand', 'gritty; forms a weak ball that breaks easily'],
    ['Sandy loam', 'gritty; holds a ball but makes almost no ribbon'],
    ['Loam', 'soft and slightly gritty; short ribbon (under 2.5 cm)'],
    ['Silt loam', 'smooth like flour; short ribbon'],
    ['Silt', 'very smooth and silky'],
    ['Sandy clay loam', 'gritty and a little sticky; ribbon 2.5 to 5 cm'],
    ['Clay loam', 'slightly sticky; ribbon 2.5 to 5 cm'],
    ['Silty clay loam', 'smooth and sticky; ribbon 2.5 to 5 cm'],
    ['Sandy clay', 'gritty and sticky; long ribbon (over 5 cm)'],
    ['Silty clay', 'smooth and very sticky; long ribbon'],
    ['Clay', 'very sticky; long ribbon (over 5 cm)']
  ];
  classes.forEach(function (c, i) {
    form.addMultipleChoiceItem()
        .setTitle('T' + (i + 1) + '. ' + c[0])
        .setHelpText(c[1])
        .setChoiceValues(groups)
        .setRequired(true);
  });

  // ----- Part 2: numbers to check -----
  form.addPageBreakItem().setTitle('Part 2 of 3: A few numbers to check');
  form.addTextItem().setTitle('N1. Maximum lime in ONE application (tonnes per hectare)')
      .setHelpText('You wrote "100000", which we think was a slip. The first agronomist said 4 to 5 t/ha.')
      .setValidation(num);
  form.addSectionHeaderItem().setTitle('When to lime other crops')
      .setHelpText('For maize you said: lime when pH (water) is below 5.5. For other crops you wrote "5.1 to 6.1". ' +
                   'Below what pH would you lime each of these crops?');
  ['Soybean', 'Sunflower', 'Millet', 'Groundnut'].forEach(function (crop, i) {
    form.addTextItem().setTitle('N' + (i + 2) + '. ' + crop + ': lime below pH').setValidation(num);
  });
  form.addTextItem().setTitle('N6. Soybean top dressing: product and rate (kg/ha), or "none"');
  form.addTextItem().setTitle('N7. Groundnut best pH range')
      .setHelpText('The draft says 5.8 to 6.0, which is very narrow. Is that right? If not, what range?');

  // ----- Part 3: Plan B budget -----
  form.addPageBreakItem().setTitle('Part 3 of 3: Plan B (small budget)').setHelpText(
    'You gave this order for a farmer who cannot afford everything: 1 certified seed, 2 fertiliser, 3 lime, 4 manure.');
  form.addMultipleChoiceItem().setTitle('B1. With a LOW budget, how many of these four can a typical farmer afford?')
      .setChoiceValues(['Only the 1st', 'The first 2', 'The first 3', 'All 4', 'Not sure']);
  form.addMultipleChoiceItem().setTitle('B2. With a MEDIUM budget, how many of these four?')
      .setChoiceValues(['Only the 1st', 'The first 2', 'The first 3', 'All 4', 'Not sure']);
  form.addParagraphTextItem().setTitle('Anything else?');

  var sheet = SpreadsheetApp.create('SoilSense ZM: follow-up questions (responses)');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());
  Logger.log('SEND THIS LINK: ' + form.shortenFormUrl(form.getPublishedUrl()));
  Logger.log('Responses spreadsheet: ' + sheet.getUrl());
}
