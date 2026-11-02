#include "golem/workpack.h"
#include <json-c/json.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "line %d: %s\n", __LINE__, #x); exit(1); } } while (0)
static void failure(const void *bytes, size_t n)
{
    golem_digest d, old;
    memset(&d, 0xa5, sizeof(d)); old = d;
    CHECK(golem_workpack_validate((golem_bytes){bytes, n}, &d, NULL) != GOLEM_OK);
    CHECK(!memcmp(&d, &old, sizeof(d)));
}
static void bad(struct json_object *o, const char *key, struct json_object *v)
{
    struct json_object *copy = NULL;
    CHECK(json_object_deep_copy(o, &copy, NULL) == 0);
    json_object_object_add(copy, key, v);
    const char *s = json_object_to_json_string_ext(copy, JSON_C_TO_STRING_PLAIN);
    failure(s, strlen(s)); json_object_put(copy);
}
int main(int argc, char **argv)
{
    CHECK(argc >= 2);
    FILE *f = fopen(argv[1], "rb"); CHECK(f);
    uint8_t data[GOLEM_WORKPACK_MAX_JSON + 1]; size_t n = fread(data, 1, sizeof(data), f);
    CHECK(!ferror(f) && feof(f) && fclose(f) == 0);
    if (argc == 3) { failure(data, n); return 0; }
    golem_digest d, exact, again; golem_diagnostic diagnostic;
    CHECK(golem_workpack_validate((golem_bytes){data,n}, &d, &diagnostic) == GOLEM_OK);
    CHECK(diagnostic.status == GOLEM_OK);
    CHECK(golem_digest_bytes((golem_bytes){data,n}, &exact) == GOLEM_OK && !memcmp(&d,&exact,sizeof(d)));
    CHECK(golem_workpack_validate((golem_bytes){data,n}, &again,NULL) == GOLEM_OK && !memcmp(&d,&again,sizeof(d)));
    CHECK(golem_workpack_validate((golem_bytes){data,n},NULL,NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(n < sizeof(data));
    data[n] = 0;
    struct json_object *o = json_tokener_parse((const char *)data); CHECK(o);
    const char *pretty = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PRETTY);
    CHECK(golem_workpack_validate((golem_bytes){(const uint8_t *)pretty,strlen(pretty)},&again,NULL) == GOLEM_OK);
    CHECK(memcmp(&d,&again,sizeof(d)) != 0);
    const char *invalid[] = {"", "{}", "[]", "null", "schema: golem.workpack.v0", "{\"x\":1,\"x\":2}",
        "{\"x\":1,\"\\u0078\":2}", "{\"x\":\"\\u0000\"}", "{\"x\":\"\xff\"}", "{}{}"};
    for (size_t i=0;i<sizeof(invalid)/sizeof(*invalid);++i) failure(invalid[i],strlen(invalid[i]));
    failure(NULL,0); failure(data,GOLEM_WORKPACK_MAX_JSON+1);
    data[n]=0; failure(data,n+1);
    const char *versions[] = {"latest","1.2","1.2.3.4","01.2.3","1.2.65536","-1.0.0","1.0.0-beta","1.0.0+build"};
    for (size_t i=0;i<sizeof(versions)/sizeof(*versions);++i) bad(o,"version",json_object_new_string(versions[i]));
    bad(o,"core_min",json_object_new_string("2.0.0"));
    bad(o,"id",json_object_new_string("../escape")); bad(o,"id",json_object_new_string("ａｂｃ"));
    bad(o,"id",json_object_new_string("a..b")); bad(o,"id",json_object_new_string("a."));
    bad(o,"publisher",json_object_new_boolean(true)); bad(o,"command",json_object_new_string("sh"));
    bad(o,"completion",json_object_new_string("DONE")); bad(o,"provenance",json_object_new_string("not-a-digest"));
    bad(o,"roles",json_tokener_parse("[\"a\",\"a\"]")); bad(o,"roles",json_tokener_parse("[null]"));
    bad(o,"roles",json_tokener_parse("[]")); bad(o,"intent",json_tokener_parse("[\"   \"]"));
    bad(o,"intent",json_tokener_parse("[\"a\\n\"]"));
    char large[258]; memset(large,'a',sizeof(large)); large[257]=0;
    struct json_object *a=json_object_new_array(); json_object_array_add(a,json_object_new_string(large)); bad(o,"intent",a);
    a=json_object_new_array();
    for (size_t i=0;i<17;++i) { char name[20]; (void)snprintf(name,sizeof(name),"role%zu",i); json_object_array_add(a,json_object_new_string(name)); }
    bad(o,"roles",a);
    /* Both sides of each independent byte/count ceiling. */
    const char *fields[] = {"id", "publisher", "intent", "roles", "capabilities", "prohibited_effects", "inputs", "evidence"};
    for (size_t field=0;field<sizeof(fields)/sizeof(*fields);++field) {
        for (size_t extra=0;extra<2;++extra) {
            struct json_object *v=NULL, *candidate=NULL;
            if (field<3) {
                size_t length=(field<2 ? 128u : 256u)+extra;
                char bounded[258]; memset(bounded,'a',length);bounded[length]=0;
                v=json_object_new_string(bounded);
                if (field==2) { a=json_object_new_array();json_object_array_add(a,v);v=a; }
            } else {
                size_t count=(field==3 ? 16u : 32u)+extra;
                v=json_object_new_array();
                for(size_t i=0;i<count;++i) { char name[20];(void)snprintf(name,sizeof(name),"item%zu",i);json_object_array_add(v,json_object_new_string(name)); }
            }
            CHECK(json_object_deep_copy(o,&candidate,NULL)==0);
            json_object_object_add(candidate,fields[field],v);
            const char *encoded=json_object_to_json_string_ext(candidate,JSON_C_TO_STRING_PLAIN);
            if(extra) failure(encoded,strlen(encoded));
            else CHECK(golem_workpack_validate((golem_bytes){(const uint8_t *)encoded,strlen(encoded)},&again,NULL)==GOLEM_OK);
            json_object_put(candidate);
        }
    }
    struct json_object *schema_copy=NULL;CHECK(json_object_deep_copy(o,&schema_copy,NULL)==0);
    json_object_object_add(schema_copy,"schema",json_object_new_string("golem.workpack.v9"));
    const char *unsupported=json_object_to_json_string(schema_copy);
    CHECK(golem_workpack_validate((golem_bytes){(const uint8_t *)unsupported,strlen(unsupported)},&again,&diagnostic)==GOLEM_ERR_UNSUPPORTED_VERSION);
    json_object_put(schema_copy);
    struct json_object *copy=NULL; CHECK(json_object_deep_copy(o,&copy,NULL)==0);
    json_object_object_del(copy,"roles"); const char *s=json_object_to_json_string(copy); failure(s,strlen(s));json_object_put(copy);
    /* Maximum input size is accepted when the extra bytes are legal whitespace. */
    memset(data+n,' ',GOLEM_WORKPACK_MAX_JSON-n);
    CHECK(golem_workpack_validate((golem_bytes){data,GOLEM_WORKPACK_MAX_JSON},&again,NULL)==GOLEM_OK);
    json_object_put(o); return 0;
}
