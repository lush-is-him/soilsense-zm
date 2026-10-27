/**
 * SoilSense ZM: questionnaire for the second agronomist, as a Google Form.
 *
 * How to use (once, about 5 minutes):
 *   1. Go to https://script.google.com and click "New project".
 *   2. Delete the empty code, paste this whole file, click Save.
 *   3. Choose "createForm" in the function box at the top and click Run.
 *   4. Allow the permissions it asks for (Google may say the app is not
 *      verified: click Advanced > Go to project. It is your own script).
 *   5. Open "Execution log" at the bottom: it prints the link to send
 *      and the link to the responses spreadsheet.
 *
 * Part 2 asks his own answers before Part 3 shows the first reviewer's
 * draft values, so his key answers are independent.
 */

function createForm() {
  var form = FormApp.create('SoilSense ZM: agronomist review');
  form.setDescription(
    'SoilSense ZM is a final-year project (ZCAS University) that gives smallholder farmers in ' +
    'Kafue District advice on soil acidity, lime and crops, from a low-cost pH probe checked ' +
    'against a free soil map. The system is rule-based: every number it uses must come from an ' +
    'expert or a published source.\n\n' +
    'About 30 to 40 minutes. Short answers are fine. Write "unsure" where that is the honest ' +
    'answer; please do not guess. Where you can, say where an answer comes from (a named ' +
    'document, or your field experience).\n\n' +
    'Progress is not saved if you close the page, so please answer in one sitting.');
  form.setCollectEmail(false);
  form.setProgressBar(true);
  form.setConfirmationMessage('Thank you. Your answers will be written into the rule tables and labelled as your expert input.');

  var num = FormApp.createTextValidation().requireNumber().setHelpText('Please enter a number').build();
  var yesNoUnsure = ['Yes', 'No', 'Unsure'];
  var agree = ['Agree', 'Disagree', 'Not sure'];

  function text(title, help, required, numeric) {
    var item = form.addTextItem().setTitle(title);
    if (help) item.setHelpText(help);
    if (required) item.setRequired(true);
    if (numeric) item.setValidation(num);
    return item;
  }
  function para(title, help) {
    var item = form.addParagraphTextItem().setTitle(title);
    if (help) item.setHelpText(help);
    return item;
  }
  function choice(title, options, help, required) {
    var item = form.addMultipleChoiceItem().setTitle(title).setChoiceValues(options).showOtherOption(false);
    if (help) item.setHelpText(help);
    if (required) item.setRequired(true);
    return item;
  }
  function section(title, help) {
    var page = form.addPageBreakItem().setTitle(title);
    if (help) page.setHelpText(help);
  }

  // ----- Part 1: about you -----
  section('Part 1 of 6: About you', 'For the dissertation. You may stay anonymous.');
  text('Name and title as you would like it written (leave blank to stay anonymous)');
  choice('May I name you and your credentials in the dissertation as a reviewer?',
         ['Yes', 'Yes, but anonymised (role only)', 'No'], null, true);
  text('Highest qualification and field', null, true);
  text('Current role and organisation');
  text('Years of experience with smallholder agronomy in Zambia', null, false, true);
  choice('Do you have experience in Lusaka Province or Kafue District?', yesNoUnsure);
  choice('Are you related to the student (Lushomo Sibalwa)?', ['No', 'Yes'], 'Asked so the dissertation can report independence honestly.', true);

  // ----- Part 2: key decisions (independent) -----
  section('Part 2 of 6: Key decisions',
          'Please answer from your own knowledge before seeing any draft values (those come in Part 4).');
  choice('When you give pH thresholds for liming and crops, which method are they in?',
         ['pH in water', 'pH in calcium chloride (CaCl2)', 'Unsure'],
         'Labs usually report CaCl2; field probes and soil maps read pH in water, about 0.5 to 0.8 higher.', true);
  text('Below what pH do you recommend lime, for maize?', 'A number, e.g. 5.5', true, true);
  text('Below what pH do you recommend lime, for other crops? (if different)');
  text('What target pH should smallholder liming aim for?', 'e.g. 5.5 to 6.5', true);
  text('Below what pH should the system give NO plan and send the farmer to a lab or extension officer?',
       'A number, e.g. 4.5', true, true);
  text('Shortest time before planting that lime can still be applied and work (months, rainfed)', 'e.g. 2', true, true);
  text('Maximum lime in one application (tonnes per hectare)', null, true, true);
  form.addGridItem()
      .setTitle('A farmer can only afford part of the inputs. In what order should they buy them?')
      .setHelpText('1st = buy first. One number per item.')
      .setRows(['Lime', 'Fertiliser', 'Certified seed', 'Manure'])
      .setColumns(['1st', '2nd', '3rd', '4th'])
      .setValidation(FormApp.createGridValidation().requireLimitOneResponsePerColumn().build())
      .setRequired(true);
  choice('For farmers who cannot afford the full lime rate, do you recommend lime at the planting station (basin)?',
         yesNoUnsure, null, true);
  text('If yes: grams of lime per planting station', 'e.g. 50');
  text('If yes: station spacing you mean (row x in-row, cm)', 'e.g. 75 x 25 for maize');
  text('If yes: is there a published source for this practice? (name it)');
  text('How large is one lima, in hectares?', 'e.g. 0.25', false, true);
  text('Soil sampling depth for a lab pH test (cm)', 'e.g. 0-20', true);

  // ----- Part 3: sorghum (no data yet) -----
  section('Part 3 of 6: Sorghum', 'The system has no sorghum data yet.');
  text('Sorghum: lowest workable pH', null, false, true);
  text('Sorghum: best pH range', 'e.g. 5.5-7.0');
  text('Sorghum: highest workable pH', null, false, true);
  text('Sorghum: rainfed planting window (months) around Kafue', 'e.g. Nov-Dec');
  text('Sorghum: basal fertiliser product and rate (kg/ha)');
  text('Sorghum: top dressing product, rate (kg/ha) and timing');
  text('Sorghum: manure rate (tonnes per hectare)');

  // ----- Part 4: confirm crop values -----
  section('Part 4 of 6: Check the draft crop values',
          'Another agronomist supplied these draft values. Please say whether you agree, and correct them where needed. ' +
          'pH thresholds use the method you chose in Part 2.');
  var crops = [
    ['Maize', '5.5', '5.5-6.8', '7.5', 'Nov-Dec', 'Compound D about 200 kg/ha', 'Urea (46% N) or CAN, two splits at 3-4 and 6-8 weeks after emergence; rate not given', '5-15'],
    ['Soybean', '5.5', '5.8-7.0', '7.5', 'Nov-Dec', 'phosphorus-based, according to soil test; rate not given', 'nil, or light ammonium nitrate; rate not given', '5-10'],
    ['Sunflower', '5.0', '6.0-7.5', '8.5', 'Dec-Jan', 'Compound D; rate not given', 'Urea or CAN plus boron and potassium; rate not given', '10-20'],
    ['Millet', '4.8', '5.5-7.0', '7.5', 'Nov-Dec', 'not specified', 'Urea; rate not given', '3-5'],
    ['Groundnut', '5.0', '5.8-6.0', '7.5', 'Nov-Dec', 'phosphorus-based; rate not given', 'Gypsum; rate not given', '5-8']
  ];
  crops.forEach(function (c) {
    form.addSectionHeaderItem().setTitle(c[0]).setHelpText(
      'Lowest workable pH ' + c[1] + ' | best ' + c[2] + ' | highest ' + c[3] + '\n' +
      'Rainfed planting: ' + c[4] + '\n' +
      'Basal: ' + c[5] + '\n' +
      'Top dressing: ' + c[6] + '\n' +
      'Manure: ' + c[7] + ' tonnes per hectare');
    choice(c[0] + ': do you agree with these values?', agree, null, true);
    para(c[0] + ': corrections, and the missing rates (basal and top dressing, kg/ha)');
  });
  choice('Should groundnut be one of the crops in the system?', yesNoUnsure);

  // ----- Part 5: lime table and soil texture -----
  section('Part 5 of 6: Lime rates and soil texture');
  form.addSectionHeaderItem().setTitle('Draft lime rates (tonnes per hectare)').setHelpText(
    'pH below 4.5:   sandy 1.0-1.5 | loamy 2.0-3.0 | clay 3.5-5.0\n' +
    'pH 4.5 to 5.5:  sandy 0.5-1.0 | loamy 1.5-2.0 | clay 2.5-3.5\n' +
    'pH 5.5 to 6.5:  sandy 0.0-0.5 | loamy 0.5-1.0 | clay 1.0-1.5\n' +
    'pH above 6.5:   none');
  choice('Do you agree with these lime rates?', agree, null, true);
  para('Corrections to the lime rates, and the source (document or field experience)');
  form.addSectionHeaderItem().setTitle('Grouping soil textures for the lime table').setHelpText(
    'Sandy: Sand, Loamy Sand, Sandy Loam\n' +
    'Loamy: Loam, Silt Loam, Silt, Sandy Clay Loam\n' +
    'Clay: Clay, Silty Clay, Sandy Clay, Clay Loam, Silty Clay Loam');
  choice('Do you agree with this grouping?', agree, null, true);
  para('Corrections to the grouping');

  // ----- Part 6: sources and review -----
  section('Part 6 of 6: Sources and scenario review');
  para('Which documents, guidelines or textbooks do you rely on? (title, year, publisher)');
  choice('Would you review about 60 to 100 test scenarios (soil pH, crop, texture, budget) and say whether the system\'s advice is right?',
         ['Yes', 'Maybe, fewer scenarios', 'No'], null, true);
  choice('Preferred format for the scenario review',
         ['Google Sheet on my phone', 'Spreadsheet on a computer', 'Printed paper', 'WhatsApp voice notes']);
  text('When could you do the scenario review?');
  para('Anything else the system must say, or must never say, to farmers?');

  // Responses go to a spreadsheet in your Drive.
  var sheet = SpreadsheetApp.create('SoilSense ZM: agronomist review (responses)');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());

  Logger.log('SEND THIS LINK to the agronomist: ' + form.shortenFormUrl(form.getPublishedUrl()));
  Logger.log('Edit the form: ' + form.getEditUrl());
  Logger.log('Responses spreadsheet: ' + sheet.getUrl());
}
