# TODO

## Test newly introduced HA services on a real server

- [ ] `came_domotic.create_user` — verify user creation with a specific group and with the default `*` group
- [ ] `came_domotic.delete_user` — verify user deletion, confirm error when trying to delete the authenticated user
- [ ] `came_domotic.change_password` — verify password change for a non-authenticated user and for the authenticated user (check that config entry credentials update automatically)
- [ ] `came_domotic.get_terminal_groups` — verify the returned list matches what the CAME server reports
