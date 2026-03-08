                                           title=user_input[CONF_FEED_NAME], data=user_input
                                                                            )

                                                                                    data_schema = vol.Schema(
                                                                                                {
                                                                                                                vol.Required(CONF_FEED_NAME, default="My Exported Calendar"): str,
                                                                                                                                vol.Required(CONF_CALENDARS): selector.EntitySelector(
                                                                                                                                                    selector.EntitySelectorConfig(
                                                                                                                                                                            domain="calendar", multiple=True
                                                                                                                                                                                                )
                                                                                                                                                                                                                ),
                                                                                                                                                                                                                            }
                                                                                                                                                                                                                                    )

                                                                                                                                                                                                                                            return self.async_show_form(
                                                                                                                                                                                                                                                        step_id="user", data_schema=data_schema, errors=errors
                                                                                                                                                                                                                                                                )
