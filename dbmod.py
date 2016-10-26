#!/usr/bin/env/python3

import sys

import mongoengine as me
import pudb
import re
from tornado import template
from terminal import Emulator
from terminal import BTN


# HOST = '127.0.0.1:8123'
HOST = 'asknidev.int.kn:23'
me.connect('orca_test', port=27017)


class CielDBSet(me.Document):
    entity_type = me.StringField()
    file = me.StringField()
    field = me.StringField()
    text = me.StringField()
    type = me.StringField()

    panel_names = me.ListField(me.StringField())


class Coords(me.EmbeddedDocument):
    row = me.IntField()
    column = me.IntField()
    length = me.IntField()

    meta = {
        'ordering': ['row', 'column', 'length']
    }


class FieldSet(me.Document):
    """Representation of an input field on the panel.
    """
    panel_name = me.StringField(required=True)
    coords = me.EmbeddedDocumentField(Coords, required=True )
    dbset = me.ReferenceField(CielDBSet, required=False)

    meta = {
        'ordering': ['panel_name', 'coords']
    }


class CielField(me.EmbeddedDocument):
    fieldset = me.ReferenceField(FieldSet)
    value = me.StringField()


class CielPanel(me.EmbeddedDocument):
    """AS/400 server response representation as seen in terminal emulator.
    The panel is stored in both, raw and html formats. Input field coordinates
    are saved through CielPanelField object.
    """
    name = me.StringField(verbose_name='CIEL panel name')
    data_raw = me.StringField(verbose_name='CIEL panel data as plain text')
    data_html = me.StringField(verbose_name='CIEL panel as a formatted data')
    fields = me.EmbeddedDocumentListField(CielField)


    meta = {
        'ordering': ['name']
    }


class CielEntity(me.Document):
    type = me.StringField(
        verbose_name='Entity type (fastpath)',
        required=True)
    name = me.StringField(required=True)
    panels = me.EmbeddedDocumentListField(CielPanel)
    descripton = me.StringField(
        verbose_name='Entity details',
        required=False)

    meta = {
        'ordering': ['fastpath']
    }

    @classmethod
    def scan_panels(cls, entity_type, entity_name):
        """Scan panels for the entity in CIEL.
        entity_type: wwartc
        entity_name: bananas-ptw
        """
        em = Emulator(visible=True)
        em.connect(HOST)
        em.ciel_login('IEVMLIR1', 'MLIIEVR1')

        em.send_str(entity_type)
        em.exec(BTN.F22)
        em.screen_skip()

        em.send_str('2')
        em.exec(BTN.TAB)

        em.send_str(entity_name)
        em.exec(BTN.ENTER)

        entity = CielEntity.objects(type=entity_type, name=entity_name).first()
        if not entity:
            entity = CielEntity(
                type=entity_type,
                name=entity_name)
            entity.save()

        panel_counter = 0
        while True:
            panel_name = em.screen_get_name()

            # Update panel if exist
            panel = None
            for p in entity.panels:
                if p.name.lower() == panel_name.lower():
                    panel = p
                    break

            if panel is not None:
                panel.data_raw = '\n'.join(em.screen_get_data(html=False))
                panel.data_html = '\n'.join(em.screen_get_data(html=True))
            else:
                panel = CielPanel(
                    name=panel_name,
                    data_raw='\n'.join(em.screen_get_data(html=False)),
                    data_html='\n'.join(em.screen_get_data(html=True))
                )
                entity.panels.append(panel)
            entity.save()

            panel.fields = []
            fields = em.field_get_bounds_all()
            for field in fields:
                flen = field['col_end'] - field['col_start']

                # pu.db
                fieldset = FieldSet.objects(
                    panel_name=panel.name,
                    coords__row=field['row'],
                    coords__column=field['col_start'],
                ).first()

                if not fieldset:
                    fieldset = FieldSet(
                        dbset=None,
                        panel_name=panel.name,
                        coords=Coords(
                            row=field['row'],
                            column=field['col_start'],
                            length=flen
                        )
                    )
                    fieldset.save()

                cielfield = CielField(
                    fieldset=fieldset,
                    value=field['value'].strip(),
                )
                panel.fields.append(cielfield)
                entity.save()

            if em.screen_contains('.*BOTTOM.*'):
                break
            else:
                em.exec(BTN.PAGE_DOWN)
                panel_counter += 1

        em.terminate()
        return entity

    @classmethod
    def scan_dbset(cls, entity_type, library_name):
        """Returns dictionary of structure:
        {
            library_name : {
            file_name : {
                field_name : {
                    'text' : '',
                    'nulls' : '',
                    'length' : '',
                    'type' : '',
                    'scale' : '',
                },
            },
            },
        }
        """
        em = Emulator(visible=True)
        em.connect(HOST)
        em.ciel_login('IEVMLIR1', 'MLIIEVR1')

        em.send_str('STRSQL')
        em.exec(BTN.F22)
        em.send_str('SELECT * FROM {}'.format(library_name))
        em.exec(BTN.F4)

        em.send_str('\t' * 10)
        em.field_set_id(2)
        em.exec(BTN.F4)

        # Library grabbing part
        data = {}
        flatdata = []

        def ensure_row_exists(row_library, row_file, row_field):
            if row_library not in data:
                data[row_library] = {}

            if row_file not in data[row_library]:
                data[row_library][row_file] = {}

            if row_field not in data[row_library][row_file]:
                data[row_library][row_file][row_field] = {}


        def grab_fields():
            rows = []

            def row_update(n, row, rows):
                if n >= len(rows):
                    rows.append(row)
                else:
                    rows[n].update(row)

            for i in range(0, 3):
                lines = em.screen_get_data(html=False)
                if em.screen_contains('.*F11=Display nulls.*'):
                    print('Display nulls')
                    for n, line in enumerate(lines[6:20]):
                        rfield = line[6:20].strip()
                        rfile = line[25:44].strip()
                        rtext = line[44:80].strip()
                        row = {'field': rfield, 'file': rfile, 'text': rtext}
                        row_update(n, row, rows)

                elif em.screen_contains('.*F11=Display type.*'):
                    print('Display type')
                    for n, line in enumerate(lines[6:20]):
                        rlib = line[45:58].strip()
                        rnulls = line[58:80].strip()
                        row = {'library': rlib, 'nulls': rnulls}
                        row_update(n, row, rows)

                elif em.screen_contains('.*F11=Display text.*'):
                    print('Display text')
                    for n, line in enumerate(lines[6:20]):
                        rtype = line[44:65].strip().lower()
                        rlength = line[65:73].strip()
                        rscale = line[73:79].strip()
                        row = {'type': rtype, 'length': rlength, 'scale': rscale}
                        row_update(n, row, rows)
                # Scroll screen right
                em.exec(BTN.F11)
            return rows

        while (not em.screen_contains('.*Bottom.*')
            and em.screen_contains('.*More\.\.\..*')):

            rows = grab_fields()
            for row in rows:
                rlib = row['library']
                rfile = row['file']
                rfield = row['field']

                if rlib not in data:
                    data[rlib] = {}

                if rfile not in data[rlib]:
                    data[rlib][rfile] = {}

                if rfield not in data[rlib][rfile]:
                    data[rlib][rfile][rfield] = {}

                item = data[rlib][rfile][rfield]
                item['text'] = row['text']
                item['type'] = row['type']
                item['length'] = row['length']
                item['scale'] = row['scale']

                flatitem = {}
                # Only if not empty item
                if len(rfile) and len(rfield):
                    flatitem['clibrary'] = (rlib.lower()).strip()
                    flatitem['cfile'] = (rfile.lower()).strip()
                    flatitem['cfield'] = (rfield.lower()).strip()
                    flatitem['ctype'] = (row['type'].lower()).strip()
                    flatitem['cnulls'] = (row['nulls'].lower()).strip()

                    try:
                        flatitem['length'] = int(row['length'])
                    except ValueError:
                        flatitem['length'] = 0

                    try:
                        flatitem['cscale'] = int(row['scale'])
                    except ValueError:
                        flatitem['cscale'] = 0

                    flatitem['ctype'] = (row['type'].strip()).lower()
                    flatitem['ctext'] = (row['text'].strip()).lower()

                    dbset_item = CielDBSet(
                        entity_type=entity_type,
                        file=flatitem['ctype'],
                        field=flatitem['cfield'],
                        text=flatitem['ctext'],
                        type=flatitem['ctype']
                    )
                    dbset_item.save()

            em.exec(BTN.PAGE_DOWN)
        return data, flatdata


def main():
    entity_type, entity_name, out_filename = sys.argv[1:4]

    def scanall():
        print('scanning fields')
        CielEntity.scan_panels(entity_type, entity_name)
        # CielEntity.scan_dbset(entity_type, 'WSAAR1P')
        print('scan finished')

    def link_dbset(entity_type, entity_name):
        print('linking a dbset')
        entity = CielEntity.objects(type=entity_type, name=entity_name).first()

        dbsets = CielDBSet.objects(entity_type=entity_type)
        re_flags = re.MULTILINE | re.DOTALL | re.IGNORECASE
        for dbset in dbsets:
            search_text = re.escape(dbset.text)
            for panel in entity.panels:
                b_found = re.search(
                    re.escape(dbset.text),
                    panel.data_raw,
                    re_flags
                )
                if b_found:
                    print('found "{}"'.format(dbset.text))
                    dbset.update(add_to_set__panel_names=panel.name)

        print('linking finished')

    def write_file(entity_type, entity_name):
        entity = CielEntity.objects(type=entity_type, name=entity_name).first()
        pdata = '<pre>'

        for panel in entity.panels:
            lines = panel.data_raw.split('\n')
            for field in panel.fields:
                fset = field.fieldset
                coo = fset.coords
                l = lines[coo.row - 1]

                col = coo.column
                candl = coo.column + coo.length + 1
                s = (
                    l[0:col] +
                    '<span class="highl">' +
                    l[col:candl] +
                    '</span>' +
                    l[candl:])
                lines[coo.row - 1] = s
                pdata += '\n'.join(lines)
            pdata += '\n' * 4
        pdata += '</pre>'

        template_panels = (
            '<html>'
            '  <head>'
            '    <style>'
            '      .highl {'
            '        color: red;'
            '      }'
            '    </style>'
            '  </head>'
            '  <body>' +
            pdata +
            '  </body>'
            '<html>'
        )

        with open(
            '{}__{}_screens.html'.format(entity_type, entity_name), 'w'
        ) as fout:
            fout.write(template_panels)

    read_entity('entity.csv')

    # CielEntity.objects().delete()
    # FieldSet.objects().delete()
    # scanall()
    # link_dbset(entity_type, entity_name)
    # write_file(entity_type, entity_name)
    # import pudb; pu.db


def write_entity(entity_name, filename='entity.csv'):
    with open(filename, 'w') as fout:
        fout.write('Article Name, {}\n'.format(entity_name))
        entity = CielEntity.objects().first()
        panels = entity.panels

        for panel in entity.panels:
            for field in panel.fields:
                if field.fieldset.dbset is not None:
                    fout.write(
                        '{},{}\n'.format(
                            field.fieldset.dbset.field,
                            field.value
                        )
                    )


def read_entity(filename):
    d = {}
    with open(filename, 'r') as fin:
        for line in fin:
            field, _, value = line.partition(',')
            v = value.strip()
            if len(v):
                d[field.lower()] = v

        em = Emulator(visible=True)
        em.connect(HOST)
        em.ciel_login('IEVMLIR1', 'MLIIEVR1')

        em.send_str('WWARTC')
        em.exec(BTN.F22)
        em.send_str('1')
        em.exec(BTN.TAB)
        em.send_str(d['name'])
        em.exec(BTN.ENTER)
        pu.db

        first_panel_name = em.screen_get_name()
        panel_count = 0

        while True:
            em.screen_clear_fields()
            panel_name = em.screen_get_name()
            for fs in FieldSet.objects(panel_name__iexact=panel_name):
                if fs.dbset:
                    if fs.dbset.field in d:
                        print('fieldname: "{}"; value: "{}"'.format(
                            fs.dbset, d[fs.dbset.field]))
                        em.cursor_move(fs.coords.row + 1, fs.coords.column + 1)
                        em.send_str(d[fs.dbset.field])

            if panel_name == first_panel_name and panel_count > 0:
                break
            else:
                em.exec(BTN.PAGE_DOWN)

            panel_count += 1

        em.terminate()


if __name__ == '__main__':

    if len(sys.argv) < 4:
        print('Usage: dbmod.py <entity_type> <entity_name> <out_filename>')
        sys.exit(1)
    else:
        try:
            main()
        except KeyboardInterrupt:
            print('Execution interrupted by user...')
            sys.exit(0)
