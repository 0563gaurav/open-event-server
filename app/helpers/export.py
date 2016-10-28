import icalendar
from flask import url_for
from icalendar import Calendar
from pentabarf.Event import Event
from pentabarf.Day import Day
from pentabarf.Person import Person
from pentabarf.Room import Room
from sqlalchemy import DATE
from sqlalchemy import asc
from sqlalchemy import cast
from sqlalchemy import func
from app.models.event import Event as EventModel

from app import db
from app.models.session import Session

from app.helpers.data_getter import DataGetter
from pentabarf.Conference import Conference


def format_timedelta(td):
    hours, remainder = divmod(td.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    hours, minutes, seconds = int(hours), int(minutes), int(seconds)
    if hours < 10:
        hours = '0%s' % int(hours)
    if minutes < 10:
        minutes = '0%s' % minutes
    if seconds < 10:
        seconds = '0%s' % seconds
    return '%s:%s' % (hours, minutes)


class ExportHelper:

    def __init__(self):
        pass

    @staticmethod
    def export_as_pentabarf(event_id):
        event = DataGetter.get_event(event_id)
        diff = (event.end_time - event.start_time)

        tz = event.timezone or 'UTC'
        tz = pytz.timezone(tz)

        conference = Conference(title=event.name, start=tz.localize(event.start_time), end=tz.localize(event.end_time),
                                days=diff.days if diff.days > 0 else 1,
                                day_change="00:00", timeslot_duration="00:15")
        dates = (db.session.query(cast(Session.start_time, DATE))
                 .filter_by(event_id=event_id)
                 .filter_by(state='accepted')
                 .filter(Session.in_trash is not True)
                 .order_by(asc(Session.start_time)).distinct().all())

        for date in dates:
            date = date[0]
            day = Day(date=date)
            microlocation_ids = list(db.session.query(Session.microlocation_id)
                                     .filter(func.date(Session.start_time) == date)
                                     .filter_by(state='accepted')
                                     .filter(Session.in_trash is not True)
                                     .order_by(asc(Session.microlocation_id)).distinct())
            for microlocation_id in microlocation_ids:
                microlocation_id = microlocation_id[0]
                microlocation = DataGetter.get_microlocation(microlocation_id)
                sessions = Session.query.filter_by(microlocation_id=microlocation_id) \
                    .filter(func.date(Session.start_time) == date) \
                    .filter_by(state='accepted')\
                    .filter(Session.in_trash is not True)\
                    .order_by(asc(Session.start_time)).all()

                room = Room(name=microlocation.name)
                for session in sessions:

                    session_event = Event(id=session.id,
                                          date=tz.localize(session.start_time),
                                          start=tz.localize(session.start_time).strftime("%H:%M"),
                                          duration=format_timedelta(session.end_time - session.start_time),
                                          track=session.track.name,
                                          abstract=session.short_abstract,
                                          title=session.title,
                                          type='Talk',
                                          description=session.long_abstract,
                                          conf_url=url_for('event_detail.display_event_detail_home',
                                                           identifier=event.identifier),
                                          full_conf_url=url_for('event_detail.display_event_detail_home',
                                                                identifier=event.identifier, _external=True),
                                          released="True" if event.schedule_published_on else "False")

                    for speaker in session.speakers:
                        person = Person(id=speaker.id, name=speaker.name)
                        session_event.add_person(person)

                    room.add_event(session_event)
                day.add_room(room)
            conference.add_day(day)

        return conference.generate("Generated by Open Event")

    @staticmethod
    def export_as_ical(event_id):
        """Takes an event id and returns the event in iCal format"""
        cal = Calendar()
        event = icalendar.Event()
        matching_event = EventModel.query.get(event_id)
        event.add('summary', matching_event.name)
        event.add('geo', (matching_event.latitude, matching_event.longitude))
        event.add('location', matching_event.location_name)
        event.add('dtstart', matching_event.start_time)
        event.add('dtend', matching_event.end_time)
        event.add('logo', matching_event.logo)
        event.add('email', matching_event.email)
        event.add('description', matching_event.description)
        event.add('url', url_for('event_detail.display_event_detail_home', identifier=matching_event.identifier, _external=True))
        cal.add_component(event)
        return cal.to_ical()
