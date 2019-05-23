#!/usr/bin/env python

import gobject
import dbus
from dbus.mainloop.glib import DBusGMainLoop
import pickle
from datetime import datetime, timedelta


class Helpers(object):
    @staticmethod
    def hours_mins(td):
        hours, rem = divmod(td.seconds, 3600)
        mins = rem / 60
        return hours, mins

    @staticmethod
    def subtract_times(td1, td2):
        if td1 >= td2:
            diff = td1 - td2
            return Helpers.hours_mins(diff)
        elif td2 > td1:
            diff = td2 - td1
            hours, mins = Helpers.hours_mins(diff)
            return -hours, -mins


class LockHandler(object):
    def __init__(self):
        self.latest_lock = None
        self.latest_unlock = None
        self.log = {}

        self.load()

    @property
    def todays_log(self):
        date = datetime.now().date()
        if not date in self.log:
            self.log[date] = {}
        return self.log[date]

    @property
    def previous_workdays_log(self):
        today = datetime.now().date()

        for i in range(1, 100):
            td = timedelta(days=i)
            prev_workday = today - td
            if prev_workday in self.log:
                return self.log[prev_workday]
        else:
            print("No workday in the last 100 days, returning None")
            return None

    def print_log(self, log):
        fmt = "%H:%M"
        arrive = log["arrive"].strftime(fmt) if "arrive" in log else None
        leave = log["leave"].strftime(fmt) if "leave" in log else None

        work_hours = None
        work_minutes = None
        work_delta_hours = None
        work_delta_minutes = None
        if arrive and leave:
            work_duration = log["leave"] - log["arrive"]
            work_duration -= timedelta(minutes=30)
            work_hours, work_minutes = Helpers.hours_mins(work_duration)
            work_delta_hours, work_delta_minutes = Helpers.subtract_times(work_duration, timedelta(hours=8))

        print("{}: {} - {} = {}h {}m ({}h {}m)".format(log["arrive"].date(),
                                                       arrive or "xx:xx",
                                                       leave or "xx:xx",
                                                       work_hours if work_hours is not None else "x",
                                                       work_minutes if work_minutes is not None else "xx",
                                                       work_delta_hours if work_delta_hours is not None else "xx",
                                                       work_delta_minutes if work_delta_minutes is not None else "xx"))

    def handle_unlock(self):
        # First unlock of the day is always arrive time, and last unlock time was previous leave time
        if not self.todays_log:
            print("-----")
            prev_log = self.previous_workdays_log
            if prev_log:
                prev_log["leave"] = self.latest_lock
                self.print_log(prev_log)

            self.todays_log["arrive"] = self.latest_unlock
            self.print_log(self.todays_log)
            prev_log = self.previous_workdays_log
            self.save()

    def save(self):
        with open("autotime.log", "w+") as f:
            pickle.dump(self.log, f)

    def load(self):
        try:
            with open("autotime.log", "r") as f:
                self.log = pickle.load(f)
            for day in sorted(self.log):
                self.print_log(self.log[day])
        except EOFError as err:
            print("No log could be loaded, initializing to empty!")

    def dbus_callback(self, bus, message):
        if message.get_member() != "ActiveChanged":
            return

        args = message.get_args_list()
        if args[0] == True:
            self.latest_lock = datetime.now()
            # print("Lock Screen at {}".format(self.latest_lock))
        else:
            self.latest_unlock = datetime.now()
            # print("Unlock Screen at {}".format(self.latest_unlock))
            self.handle_unlock()

    def setup_dbus_listener(self):
        DBusGMainLoop(set_as_default=True)
        bus = dbus.SessionBus()
        bus.add_match_string("type='signal',interface='org.gnome.ScreenSaver'")
        bus.add_message_filter(self.dbus_callback)
        mainloop = gobject.MainLoop()
        mainloop.run()

lh = LockHandler()
lh.setup_dbus_listener()
