import itertools
import numbers
from datetime import timedelta
from datetime import datetime
from collections import namedtuple
import unittest

Confirmation = namedtuple('Confirmation', 'account_number transaction_code transaction_id time_utc time')


class TimeZone:
    def __init__(self, name, offset_hours, offset_minutes):
        if name is None or len(str(name).strip()) == 0:
            raise ValueError('Timezone name cannot be empty.')

        self._name = str(name).strip()
        # technically we should check that offset is a
        if not isinstance(offset_hours, numbers.Integral):
            raise ValueError('Hour offset must be an integer.')

        if not isinstance(offset_minutes, numbers.Integral):
            raise ValueError('Minute offset must be an integer.')

        if offset_minutes > 59 or offset_minutes < -59:
            raise ValueError('Minute offset must be between -59 and 59 (inclusive).')

        # for time delta sign of minutes will be set to sign of hours
        offset = timedelta(hours=offset_hours, minutes=offset_minutes)

        # offsets are technically bounded between -12:00 and 14:00
        # see: https://en.wikipedia.org/wiki/list_of_UTC_time_offsets
        if offset < timedelta(hours=-12, minutes=0) or offset > timedelta(hours=14, minutes=0):
            raise ValueError('Offset must be between -12:00 and +14:00.')

        self._offset_hours = offset_hours
        self._offset_minutes = offset_minutes
        self._offset = offset

    @property
    def offset(self):
        return self._offset

    @property
    def name(self):
        return self._name

    def __eq__(self, other):
        return (isinstance(other, TimeZone) and
                self.name == other.name and
                self._offset_hours == other._offset_hours and
                self._offset_minutes == other._offset_minutes)

    def __repr__(self):
        return (f"TimeZone(name='{self.name}', "
                f"offset_hours={self._offset_hours}, "
                f"offset_minutes={self._offset_minutes})")

class Account:
    transaction_counter = itertools.count(100)
    _interest_rate = 0.5  # percent

    _transaction_codes = {
        'deposit': 'D',
        'withdraw': 'W',
        'interest': 'I',
        'rejected': 'X'
    }

    def __init__(self, account_number, first_name, last_name,
                 timezone=None, initial_balance=0):
        # in practice we probably would want to add checks to make sure these values are valid / non-empty
        self._account_number = account_number
        self.first_name = first_name
        self.last_name = last_name

        if timezone is None:
            timezone = TimeZone('UTC', 0, 0)
        self.timezone = timezone

        self._balance = Account.validate_real_number(initial_balance, min_value=0)

    @property
    def account_number(self):
        return self._account_number

    @property
    def first_name(self):
        return self._first_name

    @first_name.setter
    def first_name(self, value):
        self.validate_and_set_name('_first_name', value, 'First Name')

    @property
    def last_name(self):
        return self._last_name

    @last_name.setter
    def last_name(self, value):
        self.validate_and_set_name('_last_name', value, 'Last Name')

    # also going to create a full_name computed property, for ease of use
    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def balance(self):
        return self._balance

    @property
    def timezone(self):
        return self._timezone

    @timezone.setter
    def timezone(self, value):
        if not isinstance(value, TimeZone):
            raise ValueError('Time Zone must be a valid TimeZone object.')
        self._timezone = value

    @classmethod
    def get_interest_rate(cls):
        return cls._interest_rate

    @classmethod
    def set_interest_rate(cls, value):
        if not isinstance(value, numbers.Real):
            raise ValueError('Interest rate must be a real number.')

        if value < 0:
            raise ValueError('Interest rate cannot be negative.')
        cls._interest_rate = value

    def validate_and_set_name(self, attr_name, value, field_title):
        if value is None or len(str(value).strip()) == 0:
            raise ValueError(f'{field_title} cannot be empty.')
        setattr(self, attr_name, value)

    @staticmethod
    def validate_real_number(value, min_value=None):
        if not isinstance(value, numbers.Real):
            raise ValueError('Value must be a real number.')

        if min_value is not None and value < min_value:
            raise ValueError(f'Value must be at least {min_value}.')

        return value

    def generate_confirmation_code(self, transaction_code):
        # Main difficulty here is to generate the current time in UTC using this formatting:
        # YYYYMMDDHHMMSS
        dt_str = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        return f'{transaction_code}-{self.account_number}-{dt_str}-{next(Account.transaction_counter)}'

    @staticmethod
    def parse_confirmation_code(confirmation_code, preferred_time_zone=None):
        # dummy-A100-201904035145530-101
        parts = confirmation_code.split('-')
        if len(parts) != 4:
            # Really simplistic validation here - would need something better
            raise ValueError('Invalid confirmation code')

        # Unpack into separate variables
        transaction_code, account_number, raw_dt_utc, transaction_id = parts
        try:
            dt_utc = datetime.strptime(raw_dt_utc, '%Y%m%d%H%M%S')
        except ValueError as ex:
            # Probably need better error handling here
            raise ValueError('Invalid transaction datetime.') from ex

        if preferred_time_zone is None:
            preferred_time_zone = TimeZone('UTC', 0, 0)

        if not isinstance(preferred_time_zone, TimeZone):
            raise ValueError('Invalid TimeZone specified.')

        dt_preferred = dt_utc + preferred_time_zone.offset
        dt_preferred_str = f"{dt_preferred.strftime('%Y-%m-%d %H:%M:%S')} ({preferred_time_zone.name})"

        return Confirmation(account_number, transaction_code,
                            transaction_id, dt_utc.isoformat(), dt_preferred)

    def deposit(self, value):
        value = Account.validate_real_number(value, 0.01)
        transaction_code = Account._transaction_codes['deposit']
        conf_code = self.generate_confirmation_code(transaction_code)
        self._balance += value
        return conf_code

    def withdraw(self, value):
        value = Account.validate_real_number(value, 0.01)
        accepted = False
        if self.balance - value < 0:
            transaction_code = Account._transaction_codes['rejected']
        else:
            accepted = True
            transaction_code = Account._transaction_codes['withdraw']

        conf_code = self.generate_confirmation_code(transaction_code)
        if accepted:
            self._balance -= value

        return conf_code

    def pay_interest(self):
        interest = self.balance * Account.get_interest_rate() / 100
        conf_code = self.generate_confirmation_code(self._transaction_codes['interest'])
        self._balance += interest
        return conf_code

def run_tests(test_class):
    suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)

class TestAccount(unittest.TestCase):
    def setUp(self):
        self.account_number = 'A100'
        self.first_name = 'FIRST'
        self.last_name = 'LAST'
        self.tz = TimeZone('TZ', 1, 30)
        self.balance = 100.00
        self.withdraw_amount = 200

    def create_account(self):
        return Account(self.account_number, self.first_name, self.last_name, self.tz, self.balance)

    def test_create_timezone(self):
        tz = TimeZone('ABC', -1, -30)
        self.assertEqual('ABC', tz.name)
        self.assertEqual(timedelta(hours=-1, minutes=-30), tz.offset)

    def test_timezone_equal(self):
        tz1 = TimeZone('ABC', -1, -30)
        tz2 = TimeZone('ABC', -1, -30)
        self.assertEqual(tz1, tz2)

    def test_timezone_not_equal(self):
        tz = TimeZone('ABC', -1, -30)

        test_timezones = (
            TimeZone('DEF', -1, -30),
            TimeZone('ABC', -1, 0),
            TimeZone('ABC', 1, -30),
        )

        for i, test_tz in enumerate(test_timezones):
            with self.subTest(test_name=f'Test # {i}'):
                self.assertNotEqual(tz, test_tz)

    def test_create_account(self):
        a = self.create_account()
        self.assertEqual(self.account_number, a.account_number)
        self.assertEqual(self.first_name, a.first_name)
        self.assertEqual(self.last_name, a.last_name)
        self.assertEqual(self.first_name + ' ' + self.last_name, a.full_name)
        self.assertEqual(self.tz, a.timezone)
        self.assertEqual(self.balance, a.balance)

    def test_create_account_blank_first_name(self):
        self.first_name = ''
        with self.assertRaises(ValueError):
            a = self.create_account()

    def test_create_account_negative_balance(self):
        self.balance = -100.00
        with self.assertRaises(ValueError):
            a = self.create_account()

    def test_account_withdraw_ok(self):
        account_number = 'A100'
        first_name = 'FIRST'
        last_name = 'LAST'
        tz = TimeZone('TZ', 1, 30)
        balance = 100.00
        withdraw_amount = 20

        a = Account(account_number, first_name, last_name, initial_balance=balance)
        conf_code = a.withdraw(withdraw_amount)
        self.assertTrue(conf_code.startswith('W-'))
        self.assertEqual(balance - withdraw_amount, a.balance)

    def test_account_withdraw_overdraw(self):
        account_number = 'A100'
        first_name = 'FIRST'
        last_name = 'LAST'
        tz = TimeZone('TZ', 1, 30)
        balance = 100.00
        withdraw_amount = 200

        a = Account(account_number, first_name, last_name, initial_balance=balance)
        conf_code = a.withdraw(withdraw_amount)
        self.assertTrue(conf_code.startswith('X-'))
        self.assertEqual(balance, a.balance)





run_tests(TestAccount)








