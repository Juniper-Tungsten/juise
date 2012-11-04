/* ***** BEGIN LICENSE BLOCK *****
 * Version: MPL 1.1/GPL 2.0/LGPL 2.1
 *
 * The contents of this file are subject to the Mozilla Public License Version
 * 1.1 (the "License"); you may not use this file except in compliance with
 * the License. You may obtain a copy of the License at
 * http://www.mozilla.org/MPL/
 *
 * Software distributed under the License is distributed on an "AS IS" basis,
 * WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
 * for the specific language governing rights and limitations under the
 * License.
 *
 * The Original Code is Ubiquity.
 *
 * The Initial Developer of the Original Code is Mozilla.
 * Portions created by the Initial Developer are Copyright (C) 2007
 * the Initial Developer. All Rights Reserved.
 *
 * Contributor(s):
 *   Atul Varma <atul@mozilla.com>
 *
 * Alternatively, the contents of this file may be used under the terms of
 * either the GNU General Public License Version 2 or later (the "GPL"), or
 * the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
 * in which case the provisions of the GPL or the LGPL are applicable instead
 * of those above. If you wish to allow use of your version of this file only
 * under the terms of either the GPL or the LGPL, and not to allow others to
 * use your version of this file under the terms of the MPL, indicate your
 * decision by deleting the provisions above and replace them with the notice
 * and other provisions required by the GPL or the LGPL. If you do not delete
 * the provisions above, a recipient may use your version of this file under
 * the terms of any one of the MPL, the GPL or the LGPL.
 *
 * ***** END LICENSE BLOCK ***** */

// var EXPORTED_SYMBOLS = ["PrefCommands"];
jQuery(function ($) {

// const Cu = Components.utils;
// Cu.import("/ubiquity/modules/utils.js");
// Cu.import("/ubiquity/modules/ubiquity_protocol.js");

var PrefCommands = {
  COMMANDS_PREF : "extensions.ubiquity.commands",

  __feedManager: null,

  __subscribeFeed: function PC__subscribeFeed() {
    this.__feedManager.addSubscribedFeed({
      sourceUrl: this.id,
      canAutoUpdate: true,
      isBuiltIn: true,
    });
  },

  init: function PC_init(feedManager) {
    this.__feedManager = feedManager;
    this.__subscribeFeed();
  },

  setCode: function PC_setCode(code) {
    $.u.Utils.prefs.set(this.COMMANDS_PREF, code);
  },

  getCode: function PC_getCode() $.u.Utils.prefs.get(this.COMMANDS_PREF, ""),

  get id() "ubiquity://command-editor-code",
};

$.u.setPath(
  "command-editor-code",
  function makeDataUri()
    "data:application/javascript;charset=utf-8," +
    encodeURIComponent(PrefCommands.getCode()));

    $.u.PrefCommands = PrefCommands;

});
