"""Pure regressions for keyboard settings, aliases and atomic profile updates."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from shortcut_keys import (COMMANDS, ShortcutProfile, event_key, key_for,
                           normalize_key, sanitize_overrides, sequences,
                           validate_overrides)


class ShortcutKeyTests(unittest.TestCase):
    def test_commands_keep_existing_keys_and_add_three_list_actions(self):
        self.assertEqual(list(COMMANDS), ["add", "move_up", "move_down", "edit_title", "confirm",
                         "delete", "select_all", "clear", "expand", "collapse", "undo", "redo",
                         "save_draft", "find", "page"])
        self.assertEqual([key_for(action) for action in COMMANDS],
                         ["Ctrl+N", "Alt+Up", "Alt+Down", "F2", "Enter", "Delete", "Ctrl+A", "Esc",
                          "+", "-", "Ctrl+Z", "Ctrl+Y", "Ctrl+S", "Ctrl+F", "Ctrl+L"])
        self.assertEqual([command["scope"] for command in COMMANDS.values()],
                         ["目录列表"] * 10 + ["目录工作台"] * 5)
        self.assertEqual(validate_overrides({action: entry["default"]
                                           for action, entry in COMMANDS.items()}), {})

    def test_normalization_has_one_modifier_order_and_alias_spelling(self):
        examples = {" alt + control + shift + n ": "Ctrl+Alt+Shift+N",
                    "ctrl+a": "Ctrl+A", "Return": "Enter", "KP_Enter": "Enter",
                    "Escape": "Esc", "ins": "Insert", "del": "Delete", "spacebar": "Space",
                    "f12": "F12", "ctrl+Prior": "Ctrl+PageUp", "Alt+Next": "Alt+PageDown",
                    "Ctrl+Plus": "Ctrl++", "Ctrl++": "Ctrl++", "KP_Add": "+",
                    "Shift++": "+", "Ctrl+Shift++": "Ctrl++", "KP_Subtract": "-"}
        for source, expected in examples.items():
            with self.subTest(source=source):
                self.assertEqual(normalize_key(source), expected)

    def test_invalid_syntax_and_tk_pattern_injection_are_rejected(self):
        for value in [None, 12, "", " ", "Ctrl", "Ctrl+", "Ctrl+Ctrl+A", "Win+Q", "F13",
                      "<Control-a>", "Ctrl+Button-1", "Ctrl+N><Delete>", "Ctrl+A+B", "Alt+中"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_key(value)

    def test_reserved_help_windows_menus_and_clipboard_remain_native(self):
        for value in ["F1", "F10", "Ctrl+Tab", "Ctrl+Shift+Tab", "Alt+F4", "Shift+F10", "Menu",
                      "Ctrl+C", "Ctrl+V", "Ctrl+X", "Ctrl+Shift+C", "Ctrl+Shift+V", "Ctrl+Shift+X",
                      "Shift+Insert", "Ctrl+Insert", "Shift+Delete", "Alt+Tab", "Alt+Space",
                      "Ctrl+Space", "Shift+Space", "Ctrl+Shift+Space"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_overrides({"add": value})

    def test_plain_typing_and_navigation_are_never_captured(self):
        for value in ["A", "7", "Up", "Down", "Left", "Right", "Home", "End", "PageUp", "Tab",
                      "Shift+A", "Shift+7", "Shift+Left"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_overrides({"add": value})
        self.assertEqual(validate_overrides({"add": "Ctrl+M", "move_up": "Ctrl+Alt+Up"}),
                         {"add": "Ctrl+M", "move_up": "Ctrl+Alt+Up"})
        self.assertEqual(validate_overrides({"add": "Insert"}), {"add": "Insert"})

    def test_workbench_shortcuts_cannot_steal_plain_editor_keys(self):
        for action in ["undo", "redo", "save_draft", "find", "page"]:
            for key in ["Insert", "Delete", "Enter", "Esc", "Space", "+", "-"]:
                with self.subTest(action=action, key=key), self.assertRaises(ValueError):
                    validate_overrides({action: key})
        self.assertEqual(validate_overrides({"find": "F3"}), {"find": "F3"})

    def test_all_effective_actions_are_unique_including_fallbacks_and_aliases(self):
        for overrides in [{"add": "Alt+Down"}, {"add": "Ctrl+M", "move_up": "Control+m"},
                          {"move_up": "Ctrl+N"},
                          {"add": "Return"}, {"add": "Ctrl+Shift+A"}, {"add": "KP_Subtract"}]:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                validate_overrides(overrides)
        # Existing global bindings have no uppercase alias; Shift+Z remains free.
        self.assertEqual(validate_overrides({"add": "Ctrl+Shift+Z"}), {"add": "Ctrl+Shift+Z"})
        self.assertEqual(validate_overrides({"confirm": "F3", "add": "Return"}),
                         {"confirm": "F3", "add": "Enter"})

    def test_global_keys_preserve_text_selection_and_word_navigation(self):
        for action in ["undo", "redo", "save_draft", "find", "page"]:
            for base in ["Left", "Right", "Up", "Down", "Home", "End", "PageUp", "PageDown"]:
                for modifiers in ["Ctrl", "Ctrl+Shift"]:
                    with self.subTest(action=action, base=base, modifiers=modifiers), self.assertRaises(ValueError):
                        validate_overrides({action: f"{modifiers}+{base}"})
            for key in ["Ctrl+A", "Ctrl+Shift+A"]:
                with self.subTest(action=action, key=key), self.assertRaises(ValueError):
                    validate_overrides({"select_all": "Ctrl+Q", action: key})
        # Tree-local commands do not intercept the Entry/Text bindings.
        self.assertEqual(validate_overrides({"add": "Ctrl+Left"}), {"add": "Ctrl+Left"})
        self.assertEqual(validate_overrides({"select_all": "Ctrl+Q", "add": "Ctrl+A"}),
                         {"select_all": "Ctrl+Q", "add": "Ctrl+A"})

    def test_unsafe_global_overrides_fall_back_without_losing_other_settings(self):
        self.assertEqual(sanitize_overrides({"select_all": "Ctrl+Q", "find": "Ctrl+A",
                                            "page": "Ctrl+Shift+Left", "add": "Ctrl+M"}),
                         {"select_all": "Ctrl+Q", "add": "Ctrl+M"})

    def test_sanitization_recovers_valid_entries_without_mutating_input(self):
        raw = {"unknown": "Ctrl+O", "add": "Ctrl+m", "move_up": "Up", "find": "Ctrl+K",
               "page": ["bad"], "confirm": "Return"}
        self.assertEqual(sanitize_overrides(raw), {"add": "Ctrl+M", "find": "Ctrl+K"})
        self.assertEqual(raw["add"], "Ctrl+m")
        self.assertEqual(raw["page"], ["bad"])
        for value in [None, [], "Ctrl+N", 1]:
            self.assertEqual(sanitize_overrides(value), {})

    def test_sanitization_rechecks_defaults_restored_by_conflicting_entries(self):
        # move_down conflicts with the accepted add; falling back to Alt+Down
        # then invalidates move_up, which must also fall back safely.
        raw = {"add": "Ctrl+M", "move_up": "Alt+Down", "move_down": "Ctrl+M",
               "find": "Ctrl+K"}
        expected = {"add": "Ctrl+M", "find": "Ctrl+K"}
        self.assertEqual(sanitize_overrides(raw), expected)
        self.assertEqual(sanitize_overrides(dict(reversed(list(raw.items())))), expected)
        self.assertEqual(validate_overrides(expected), expected)

    def test_sanitization_keeps_valid_swaps_and_alias_conflicts_fall_back(self):
        swap = {"move_up": "Alt+Down", "move_down": "Alt+Up"}
        self.assertEqual(sanitize_overrides(swap), swap)
        self.assertEqual(validate_overrides(swap), swap)
        self.assertEqual(sanitize_overrides({"add": "Ctrl+Shift+A", "find": "Ctrl+K"}),
                         {"find": "Ctrl+K"})

    def test_only_unchanged_defaults_keep_legacy_tk_aliases(self):
        self.assertEqual(sequences("add"), ("<Control-n>",))
        self.assertEqual(sequences("add", {"add": "Insert"}), ("<Insert>",))
        self.assertEqual(sequences("confirm"), ("<Return>", "<KP_Enter>"))
        self.assertEqual(sequences("clear"), ("<Escape>",))
        self.assertEqual(sequences("select_all"), ("<Control-a>", "<Control-A>"))
        self.assertEqual(sequences("expand"), ("<plus>", "<KP_Add>"))
        self.assertEqual(sequences("collapse"), ("<minus>", "<KP_Subtract>"))
        self.assertEqual(sequences("move_up"), ("<Alt-Up>",))
        self.assertEqual(sequences("undo"), ("<Control-z>",))
        self.assertEqual(sequences("redo"), ("<Control-y>",))
        self.assertEqual(sequences("save_draft"), ("<Control-s>",))
        self.assertEqual(sequences("find"), ("<Control-f>",))
        self.assertEqual(sequences("page"), ("<Control-l>",))
        self.assertEqual(sequences("add", {"confirm": "F3", "add": "Enter"}), ("<Return>",))
        self.assertEqual(sequences("confirm", {"confirm": "Ctrl+K"}), ("<Control-k>",))
        self.assertEqual(sequences("add", {"add": "Ctrl+Shift+N"}), ("<Control-Shift-N>",))

    def test_event_capture_handles_windows_modifiers_and_keyboard_aliases(self):
        cases = [("n", 0x4, "Ctrl+N"), ("N", 0x4 | 0x1, "Ctrl+Shift+N"),
                 ("Up", 0x8, "Alt+Up"), ("Down", 0x20000, "Alt+Down"),
                 ("Return", 0, "Enter"), ("KP_Enter", 0, "Enter"),
                 ("plus", 0x1, "+"), ("KP_Add", 0, "+"), ("plus", 0x5, "Ctrl++"),
                 ("KP_Subtract", 0, "-"), ("Escape", 0, "Esc"),
                 ("ISO_Left_Tab", 0x4, "Ctrl+Shift+Tab"), ("A", 0x2 | 0x4, "Ctrl+A")]
        for keysym, state, expected in cases:
            with self.subTest(keysym=keysym, state=state):
                self.assertEqual(event_key(SimpleNamespace(keysym=keysym, state=state)), expected)
        for keysym in ["Shift_L", "Control_R", "Alt_L", "Super_L", "ISO_Level3_Shift",
                       "bracketleft", "??", "中"]:
            self.assertIsNone(event_key(SimpleNamespace(keysym=keysym, state=0)))
        self.assertIsNone(event_key(SimpleNamespace()))
        self.assertIsNone(event_key(SimpleNamespace(keysym="A", state="bad")))


class ShortcutProfileTests(unittest.TestCase):
    def test_save_precedes_mutation_and_listener_notification(self):
        events = []
        profile = ShortcutProfile(save=lambda updated: events.append(("save", updated, profile.overrides)))
        profile.subscribe(lambda: events.append(("notify", profile.overrides)))
        self.assertTrue(profile.editable)
        profile.set_key("add", "ctrl+m")
        self.assertEqual(events, [("save", {"add": "Ctrl+M"}, {}),
                                  ("notify", {"add": "Ctrl+M"})])
        self.assertEqual(profile.key("add"), "Ctrl+M")
        self.assertEqual(profile.sequences("add"), ("<Control-m>",))

    def test_failed_settings_write_preserves_profile_and_does_not_notify(self):
        save = Mock(side_effect=OSError("synthetic settings write failure"))
        listener = Mock()
        profile = ShortcutProfile({"add": "Ctrl+M"}, save=save)
        profile.subscribe(listener)
        with self.assertRaises(OSError):
            profile.set_key("add", "Ctrl+K")
        with self.assertRaises(OSError):
            profile.reset()
        self.assertEqual(profile.overrides, {"add": "Ctrl+M"})
        self.assertEqual(profile.key("add"), "Ctrl+M")
        self.assertEqual(save.call_count, 2)
        listener.assert_not_called()

    def test_conflicting_or_reserved_edits_never_reach_the_settings_writer(self):
        save, listener = Mock(), Mock()
        profile = ShortcutProfile(save=save)
        profile.subscribe(listener)
        for key in ["Alt+Down", "Ctrl+Shift+A", "F1", "Ctrl+C", "A"]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                profile.set_key("add", key)
        with self.assertRaises(ValueError):
            profile.set_key("unknown", "Ctrl+N")
        self.assertEqual(profile.overrides, {})
        save.assert_not_called()
        listener.assert_not_called()

    def test_reset_one_and_all_persist_sparse_defaults(self):
        save, listener = Mock(), Mock()
        profile = ShortcutProfile({"add": "Ctrl+M", "find": "Ctrl+K"}, save=save)
        profile.subscribe(listener)
        profile.reset("add")
        self.assertEqual(profile.overrides, {"find": "Ctrl+K"})
        self.assertEqual(profile.key("add"), "Ctrl+N")
        profile.reset()
        self.assertEqual(profile.overrides, {})
        self.assertEqual(save.call_args_list[0].args, ({"find": "Ctrl+K"},))
        self.assertEqual(save.call_args_list[1].args, ({},))
        self.assertEqual(listener.call_count, 2)

    def test_reset_rejects_a_default_still_used_by_another_custom_action(self):
        save, listener = Mock(), Mock()
        profile = ShortcutProfile({"confirm": "F3", "add": "Enter"}, save=save)
        profile.subscribe(listener)
        with self.assertRaises(ValueError):
            profile.reset("confirm")
        self.assertEqual(profile.overrides, {"confirm": "F3", "add": "Enter"})
        save.assert_not_called()
        listener.assert_not_called()
        profile.reset()
        self.assertEqual(profile.overrides, {})

    def test_unchanged_key_is_a_noop_and_returned_settings_are_a_copy(self):
        save, listener = Mock(), Mock()
        profile = ShortcutProfile({"add": "Ctrl+M"}, save=save)
        profile.subscribe(listener)
        copy = profile.overrides
        copy["add"] = "Alt+Down"
        profile.set_key("add", "Control+m")
        profile.set_key("find", "Ctrl+F")
        self.assertEqual(profile.overrides, {"add": "Ctrl+M"})
        save.assert_not_called()
        listener.assert_not_called()

    def test_subscriptions_are_unique_removable_and_close_releases_callbacks(self):
        save, first, second = Mock(), Mock(), Mock()
        profile = ShortcutProfile(save=save)
        profile.subscribe(first)
        profile.subscribe(first)
        profile.subscribe(second)
        profile.unsubscribe(second)
        profile.unsubscribe(second)
        profile.set_key("add", "Ctrl+M")
        first.assert_called_once_with()
        second.assert_not_called()
        profile.close()
        self.assertFalse(profile.editable)
        with self.assertRaises(ValueError):
            profile.set_key("add", "Ctrl+K")
        self.assertEqual(profile.key("add"), "Ctrl+M")
        self.assertEqual(first.call_count, 1)

    def test_profile_without_writer_is_read_only(self):
        profile = ShortcutProfile({"add": "Ctrl+M"})
        self.assertFalse(profile.editable)
        with self.assertRaises(ValueError):
            profile.set_key("add", "Insert")
        with self.assertRaises(ValueError):
            profile.reset()
        self.assertEqual(profile.overrides, {"add": "Ctrl+M"})


if __name__ == "__main__":
    unittest.main()
